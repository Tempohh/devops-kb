---
title: "Google Cloud Architecture Framework"
slug: well-architected
category: cloud/gcp
tags: [gcp, architecture-framework, well-architected, pillars, reliability, security, cost-optimization, operational-excellence, system-design, performance]
search_keywords: [Google Cloud Architecture Framework, GCAF, GCP well-architected, framework architettura GCP, 6 pillars GCP, system design GCP, operational excellence GCP, security GCP framework, reliability GCP, cost optimization GCP, performance optimization GCP, Architecture Center GCP, Google Cloud best practices, WAF GCP, well-architected GCP, framework cloud GCP, design principles GCP, GCP architecture review, Google architecture pillars, pilastri architettura Google Cloud, GCP maturity model, cloud architecture framework confronto, AWS WAF GCP, Azure Well-Architected GCP]
parent: cloud/gcp/fondamentali/_index
related: [cloud/aws/fondamentali/well-architected, cloud/azure/fondamentali/well-architected, cloud/gcp/fondamentali/panoramica, cloud/gcp/fondamentali/shared-responsibility]
official_docs: https://cloud.google.com/architecture/framework
status: complete
difficulty: beginner
last_updated: 2026-03-29
---

# Google Cloud Architecture Framework

Il **Google Cloud Architecture Framework** (GCAF) è la guida ufficiale di Google per progettare e valutare workload cloud **sicuri, affidabili, performanti e ottimizzati nei costi**. Analogo all'AWS Well-Architected Framework e all'Azure Well-Architected Framework, il GCAF si articola in **6 pilastri** e fornisce principi di design, best practice e strumenti di assessment.

**Quando usare il GCAF:**
- Prima di progettare una nuova architettura su GCP — come checklist guida
- Come framework per condurre **architecture review** su workload esistenti
- Per standardizzare le conversazioni tra team di sviluppo, operations e sicurezza
- Per prepararsi a certificazioni GCP (Cloud Architect, Cloud Engineer)

**Dove trovarlo:** [Google Cloud Architecture Center](https://cloud.google.com/architecture) raccoglie framework, pattern architetturali e reference architectures pronti all'uso.

---

## I 6 Pilastri

```
Google Cloud Architecture Framework — 6 Pillars

  1. System Design     2. Operational       3. Security,
                          Excellence            Privacy &
                                               Compliance
  ┌────────────┐      ┌────────────┐       ┌────────────┐
  │ Architettu-│      │ Operazioni │       │ Sicurezza  │
  │ ra solida, │      │ automatiz.,│       │ a tutti i  │
  │ scalabile  │      │ osservabil.│       │ livelli    │
  │ e modulare │      │ continua   │       │            │
  └────────────┘      └────────────┘       └────────────┘

  4. Reliability       5. Cost               6. Performance
                          Optimization          Optimization
  ┌────────────┐      ┌────────────┐       ┌────────────┐
  │ Resilienza,│      │ Eliminare  │       │ Latenza    │
  │ HA e       │      │ sprechi,   │       │ bassa,     │
  │ disaster   │      │ right-size │       │ throughput │
  │ recovery   │      │ continuo   │       │ ottimale   │
  └────────────┘      └────────────┘       └────────────┘
```

!!! note "Differenza rispetto ad AWS WAF"
    Il GCAF separa **System Design** come pilastro autonomo (principi architetturali di base come modularità, loose coupling, disasterproof design), mentre AWS lo tratta come trasversale ai pilastri. GCP chiama **Performance Optimization** ciò che AWS chiama *Performance Efficiency*. La struttura a 6 pilastri rimane però analoga nelle intenzioni.

---

## 1. System Design

> *"Design systems that are modular, scalable, and able to evolve over time."*

Il pilastro **System Design** riguarda le scelte architetturali fondamentali: come strutturare un sistema affinché sia scalabile, manutenibile e robusto nel lungo periodo.

**Principi di design:**
- **Loose coupling** — componenti disaccoppiati tramite API, code di messaggi o eventi: un componente può fallire senza impattare gli altri
- **Design for failure** — ogni componente può fallire; progettare il sistema affinché gestisca i fallimenti in modo graceful
- **Scalabilità orizzontale** — preferire N istanze piccole a 1 istanza grande; permette auto scaling elastico
- **Stateless where possible** — componenti stateless scalano senza complicazioni di sincronizzazione dello stato
- **Separation of concerns** — frontend, backend, dati e infrastruttura devono evolvere indipendentemente

**Pattern architetturali su GCP:**

| Pattern | Servizi GCP | Quando usarlo |
|---------|-------------|---------------|
| **Microservizi** | Cloud Run, GKE, Pub/Sub | Sistemi complessi con team autonomi |
| **Event-driven** | Pub/Sub, Eventarc, Cloud Functions | Integrazione asincrona, disaccoppiamento |
| **CQRS + Event Sourcing** | Pub/Sub, Firestore, BigQuery | Write-heavy + read-heavy separati |
| **Serverless** | Cloud Functions, Cloud Run | Workload burst-y, costo per esecuzione |
| **Data-intensive** | BigQuery, Dataflow, Dataproc | Pipeline analytics, ML a larga scala |

```yaml
# Esempio: architettura event-driven con Pub/Sub
# Pub/Sub topic per ordini
resource "google_pubsub_topic" "orders" {
  name = "orders-topic"
  message_retention_duration = "86400s"  # 24h
}

# Subscription per il servizio di processing
resource "google_pubsub_subscription" "orders_processing" {
  name  = "orders-processing-sub"
  topic = google_pubsub_topic.orders.name

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.orders_dlq.id
    max_delivery_attempts = 5
  }
}
```

```bash
# Pubblicare un messaggio su Pub/Sub (test di integrazione)
gcloud pubsub topics publish orders-topic \
    --message='{"order_id":"12345","amount":99.90,"currency":"EUR"}'

# Verificare che il messaggio sia ricevuto dalla subscription
gcloud pubsub subscriptions pull orders-processing-sub \
    --limit=5 \
    --auto-ack
```

!!! tip "API-first design"
    Definisci le API (REST o gRPC) **prima** di implementare i servizi. Tools: **Cloud Endpoints** o **Apigee** per gestione API; **Protocol Buffers** per API gRPC type-safe e forward-compatible.

!!! warning "Evitare il distributed monolith"
    Microservizi che si chiamano in catena sincrona (`A → B → C → D`) reintroducono accoppiamento e amplificano la latenza. Preferire pattern asincroni (Pub/Sub, Eventarc) per comunicazione non critica in termini di latenza.

---

## 2. Operational Excellence

> *"Run and improve workloads effectively through automation, observability, and continuous improvement."*

**Principi di design:**
- **Automate everything** — IaC (Terraform/Config Connector), CI/CD (Cloud Build), configurazione (Config Management)
- **Observability before go-live** — metriche, log, trace e allarmi devono essere pronti prima del deploy in produzione
- **Small, frequent, reversible changes** — deploy incrementali con possibilità di rollback automatico
- **Runbook as code** — procedure operative in Cloud Workflows o script versionati
- **Blameless post-mortem** — cultura di apprendimento dagli incidenti

**Osservabilità su GCP — Google Cloud Observability (ex Stackdriver):**

| Tool | Funzione | Equivalente AWS |
|------|----------|-----------------|
| **Cloud Monitoring** | Metriche, dashboard, alerting | CloudWatch Metrics |
| **Cloud Logging** | Log centralizzati, query con Log Analytics | CloudWatch Logs |
| **Cloud Trace** | Distributed tracing | X-Ray |
| **Cloud Profiler** | Profiling CPU/memory in produzione | CodeGuru Profiler |
| **Error Reporting** | Aggregazione e notifica errori applicativi | CloudWatch Logs Insights |

```bash
# Creare un alerting policy su Cloud Monitoring (CPU > 80%)
gcloud monitoring policies create \
    --notification-channels=CHANNEL_ID \
    --display-name="High CPU Alert" \
    --condition-display-name="CPU > 80%" \
    --condition-filter='resource.type="gce_instance" AND metric.type="compute.googleapis.com/instance/cpu/utilization"' \
    --condition-threshold-value=0.8 \
    --condition-threshold-comparison=COMPARISON_GT \
    --condition-duration=120s

# Creare un log-based metric (es. contare errori HTTP 5xx)
gcloud logging metrics create http_5xx_errors \
    --description="Conteggio risposte HTTP 5xx" \
    --log-filter='resource.type="gce_instance" httpRequest.status>=500'
```

```yaml
# Cloud Build trigger per CI/CD automatico su push a main
# cloudbuild.yaml
steps:
  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'europe-west8-docker.pkg.dev/$PROJECT_ID/myapp/api:$SHORT_SHA', '.']

  # Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'europe-west8-docker.pkg.dev/$PROJECT_ID/myapp/api:$SHORT_SHA']

  # Deploy su Cloud Run
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'api-service'
      - '--image=europe-west8-docker.pkg.dev/$PROJECT_ID/myapp/api:$SHORT_SHA'
      - '--region=europe-west8'
      - '--platform=managed'

options:
  logging: CLOUD_LOGGING_ONLY
```

!!! tip "SLOs con Cloud Monitoring"
    Definisci **SLO (Service Level Objectives)** direttamente in Cloud Monitoring: scegli un SLI (es. latenza p99 < 500ms), imposta l'obiettivo (es. 99.9%), e ottieni burn rate alerts automatici che avvisano prima che l'SLO venga violato.

---

## 3. Security, Privacy and Compliance

> *"Protect your workloads and data from unauthorized access and ensure compliance with regulatory requirements."*

**Principi di design:**
- **Defense in depth** — sicurezza a ogni livello: rete, identità, applicazione, dati
- **Zero trust** — nessuna rete è considerata sicura; verificare sempre identità e autorizzazione
- **Least privilege** — IAM con permessi minimi necessari; mai ruoli primitivi (Owner/Editor) in produzione
- **Encrypt everywhere** — dati cifrati a riposo (CMEK con Cloud KMS) e in transito (TLS 1.2+)
- **Shift left on security** — sicurezza nel ciclo di sviluppo (SAST, dependency scanning in CI/CD)

**Strumenti di sicurezza GCP:**

| Tool | Funzione |
|------|----------|
| **Security Command Center (SCC)** | Visibilità centralizzata su risorse, vulnerabilità, minacce (equivalente AWS Security Hub) |
| **Cloud Armor** | WAF e DDoS protection a livello applicativo (equivalente AWS Shield + WAF) |
| **Cloud KMS / Cloud HSM** | Gestione chiavi di cifratura (bring-your-own-key, hardware security module) |
| **Secret Manager** | Secrets management (equivalente AWS Secrets Manager) |
| **VPC Service Controls** | Perimetro di sicurezza che impedisce data exfiltration tra project |
| **Binary Authorization** | Garantisce che solo immagini container firmate e approvate vengano deployate su GKE |
| **Chronicle SIEM** | SIEM cloud-native per threat detection avanzata |

```bash
# Abilitare Security Command Center standard
gcloud services enable securitycenter.googleapis.com

# Listare findings critici da SCC
gcloud scc findings list \
    --organization=ORG_ID \
    --filter="state=ACTIVE AND severity=CRITICAL" \
    --format="table(name,category,resourceName,eventTime)"

# Creare un secret in Secret Manager
gcloud secrets create db-password \
    --replication-policy=automatic \
    --data-file=- <<< "my-secure-password-here"

# Concedere accesso al secret a un service account specifico
gcloud secrets add-iam-policy-binding db-password \
    --member="serviceAccount:backend-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Leggere un secret da un'applicazione (in produzione: via libreria client)
gcloud secrets versions access latest --secret=db-password
```

```yaml
# Esempio: Binary Authorization policy per GKE
# Richiede attestazione "production-approved" per tutti i deploy
admissionWhitelistPatterns: []
clusterAdmissionRules:
  europe-west8.my-prod-cluster:
    evaluationMode: REQUIRE_ATTESTATION
    enforcementMode: ENFORCED_BLOCK_AND_AUDIT_LOG
    requireAttestationsBy:
      - projects/my-project/attestors/production-approved
defaultAdmissionRule:
  evaluationMode: ALWAYS_DENY
  enforcementMode: ENFORCED_BLOCK_AND_AUDIT_LOG
```

!!! warning "VPC Service Controls per ambienti multi-project"
    Senza VPC Service Controls, un service account con accesso a BigQuery in un project può esfiltrare dati verso un BigQuery in un project non autorizzato. I **service perimeters** bloccano questo scenario anche se l'IAM è configurato correttamente. Essenziale per ambienti con dati sensibili (PII, PCI, HIPAA).

!!! tip "Workload Identity Federation per CI/CD"
    Non usare chiavi JSON di service account per GitHub Actions o GitLab CI. Configurare **Workload Identity Federation** per permettere alla pipeline CI/CD di assumere un service account GCP tramite OIDC — senza credenziali a lungo termine da ruotare o proteggere.

```bash
# Setup Workload Identity Federation per GitHub Actions
# 1. Creare il Workload Identity Pool
gcloud iam workload-identity-pools create github-pool \
    --location=global \
    --display-name="GitHub Actions Pool"

# 2. Creare il Provider OIDC per GitHub
gcloud iam workload-identity-pools providers create-oidc github-provider \
    --location=global \
    --workload-identity-pool=github-pool \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='my-org/my-repo'"

# 3. Concedere il binding al service account
gcloud iam service-accounts add-iam-policy-binding deploy-sa@my-project.iam.gserviceaccount.com \
    --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/my-org/my-repo"
```

---

## 4. Reliability

> *"Design and operate workloads that meet your availability and resilience requirements."*

**Principi di design:**
- **Define SLOs first** — stabilire obiettivi di affidabilità misurabili prima di progettare l'infrastruttura
- **Design for graceful degradation** — il sistema deve funzionare anche in modalità ridotta, non collassare completamente
- **Test failure modes** — chaos engineering, inject faults in staging e produzione
- **Automate recovery** — health checks, auto healing, auto scaling, automatic failover
- **Manage toil** — ridurre lavoro manuale ripetitivo attraverso automazione (principio SRE)

**Concetti fondamentali:**

| Termine | Definizione |
|---------|-------------|
| **SLI** (Service Level Indicator) | Metrica che misura il comportamento del servizio (es. % richieste con latenza < 200ms) |
| **SLO** (Service Level Objective) | Target sull'SLI (es. 99.9% richieste < 200ms nel rolling month) |
| **SLA** (Service Level Agreement) | Accordo contrattuale con conseguenze se SLO viene violato |
| **Error Budget** | Quanto "spazio per fallire" rimane prima di violare l'SLO |
| **MTTR** | Mean Time To Recovery — quanto velocemente si ripristina |
| **RTO / RPO** | Recovery Time / Point Objective — target per disaster recovery |

**Strategie di Disaster Recovery su GCP:**

| Strategia | RTO / RPO | Costo | Pattern GCP |
|-----------|-----------|-------|-------------|
| **Backup & Restore** | Ore | $ | Cloud Storage + Cloud SQL automated backups |
| **Warm Standby** | Minuti | $$ | Cloud SQL replica cross-region, GKE multi-region |
| **Hot Standby** | Secondi-minuti | $$$ | Cloud Spanner global, Memorystore replication |
| **Active-Active** | < 1s | $$$$ | Cloud Spanner, Global Load Balancer multi-region |

```bash
# Configurare Cloud SQL con replica cross-region per DR
gcloud sql instances create my-db-replica \
    --master-instance-name=my-db-primary \
    --region=europe-west3 \
    --database-version=POSTGRES_15 \
    --tier=db-n1-standard-2

# Verificare stato replica
gcloud sql instances describe my-db-replica \
    --format="value(replicaConfiguration.mysqlReplicaConfiguration)"

# Promuovere replica a primary (failover manuale)
gcloud sql instances promote-replica my-db-replica

# Configurare Cloud Run con minimum instances per evitare cold start
gcloud run services update my-service \
    --region=europe-west8 \
    --min-instances=2 \
    --max-instances=100
```

```yaml
# GKE: PodDisruptionBudget per garantire disponibilità durante rolling updates
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2  # Almeno 2 pod sempre disponibili
  selector:
    matchLabels:
      app: api

---
# GKE: HorizontalPodAutoscaler per scaling automatico
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

!!! tip "Error Budget Policy"
    Quando l'error budget scende sotto il 50%: bloccare deploy non critici e prioritizzare stabilità. Sotto il 10%: freeze totale dei feature deploy, solo fix di affidabilità. Documentare la policy prima di un incidente — non durante.

!!! warning "Cloud SQL non è automaticamente Multi-AZ"
    Di default Cloud SQL crea un'istanza **zonale**. Abilitare **High Availability** (HA) esplicitamente nella configurazione: aggiunge una replica standby in un'altra zona con failover automatico in 60-120 secondi. Costo circa 2x, ma necessario per qualsiasi workload di produzione.

---

## 5. Cost Optimization

> *"Run your workloads to maximize business value and minimize costs."*

**Principi di design:**
- **Measure and monitor** — visibilità granulare sui costi per team/workload prima di ottimizzare
- **Right-size continuously** — non provisioning "per sicurezza"; usare metriche reali per dimensionare
- **Use managed services** — eliminare overhead operativo riduce il costo totale di gestione
- **Optimize storage tiers** — dati raramente accessibili non devono stare nello storage più costoso
- **Commit when stable** — workload stabili e prevedibili beneficiano di CUD (Committed Use Discounts)

**Meccanismi di risparmio GCP:**

| Meccanismo | Dettaglio | Risparmio |
|-----------|-----------|-----------|
| **Sustained Use Discounts (SUD)** | Automatico per VM usate > 25% del mese su Compute Engine | Fino al 30% |
| **Committed Use Discounts (CUD)** | Impegno 1 o 3 anni su vCPU/memoria o servizi specifici | Fino al 57% (1yr) / 70% (3yr) |
| **Spot VMs** | VM interrompibili con preavviso 30s (ex Preemptible) | Fino all'88% |
| **Cloud Run** | Billing per ms di CPU/memoria effettiva, scale-to-zero | Ideale per traffic burst-y |
| **Committed Use (BigQuery)** | Slot commitments per query analytics intense | Variabile vs on-demand |
| **Coldline / Archive Storage** | Per dati raramente accessibili in Cloud Storage | Fino a 95% vs Standard |

```bash
# Analizzare costi per label con Billing Export su BigQuery
# (configurare export in Console: Billing > Billing Export > BigQuery)

# Query di esempio: top 10 servizi per costo del mese corrente
# Eseguire in BigQuery console
# SELECT service.description, SUM(cost) as total_cost
# FROM `my-billing-project.billing_dataset.gcp_billing_export_v1_*`
# WHERE DATE(usage_start_time) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
# GROUP BY 1 ORDER BY 2 DESC LIMIT 10

# Attivare Recommender per suggerimenti rightsizing automatici
gcloud services enable recommender.googleapis.com

# Visualizzare raccomandazioni rightsizing VM
gcloud recommender recommendations list \
    --recommender=google.compute.instance.MachineTypeRecommender \
    --location=europe-west8-b \
    --project=my-project-id \
    --format="table(name,description,stateInfo.state)"

# Convertire VM on-demand in Spot per ambienti non-prod
gcloud compute instances set-scheduling my-vm \
    --zone=europe-west8-b \
    --provisioning-model=SPOT \
    --instance-termination-action=STOP
```

```bash
# Creare un budget con notifica via email
gcloud billing budgets create \
    --billing-account=BILLING_ACCOUNT_ID \
    --display-name="Q1-2026 Budget" \
    --budget-amount=5000EUR \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0 \
    --all-updates-rule-monitoring-notification-channels=CHANNEL_ID

# Listare budget attivi
gcloud billing budgets list \
    --billing-account=BILLING_ACCOUNT_ID
```

!!! tip "Labels obbligatorie come policy org"
    Imposta un **Organization Policy** (`constraints/compute.requireLabels`) per richiedere label specifiche (es. `team`, `environment`, `cost-center`) su ogni risorsa. Senza questa policy, i costi diventano difficili da attribuire a team o workload specifici.

!!! warning "Attenzione ai costi nascosti di rete"
    Il **network egress** è spesso la sorpresa più grande in fattura: traffico dati da GCP verso internet, tra regioni diverse, o verso altri cloud provider. Usare **Premium Network Tier** solo dove necessario; **Standard Tier** per workload non latency-sensitive riduce i costi di rete.

---

## 6. Performance Optimization

> *"Use resources efficiently to meet workload demands and maintain efficiency as requirements evolve."*

**Principi di design:**
- **Choose the right resource type** — istanza, serverless, GPU, TPU: ogni workload ha il tipo ottimale
- **Measure before optimizing** — profiling reale prima di qualsiasi ottimizzazione prematura
- **Use caching strategically** — ridurre latenza e carico su backend con caching in-memory e CDN
- **Design for data locality** — collocare compute vicino ai dati riduce latenza e costi di network
- **Exploit managed services** — Spanner, BigQuery, Bigtable sono ottimizzati internamente in modi difficili da replicare

**Strumenti di ottimizzazione delle performance:**

| Strumento | Funzione |
|-----------|----------|
| **Cloud Profiler** | Profiling CPU/heap in produzione senza overhead significativo |
| **Cloud Trace** | Latenza end-to-end, identificazione bottleneck in sistemi distribuiti |
| **Memorystore** | Redis/Valkey managed per caching ad alta velocità (< 1ms latenza) |
| **Cloud CDN** | CDN integrato con Cloud Load Balancing per contenuti statici e dinamici |
| **Global Load Balancer** | Routing anycast verso il backend più vicino all'utente, globalmente |
| **Bigtable** | Database NoSQL per bassa latenza (< 1ms) a scala petabyte |
| **AlloyDB** | PostgreSQL managed con ottimizzazioni hardware (column-engine per analytics) |

```bash
# Configurare Memorystore Redis per caching
gcloud redis instances create app-cache \
    --size=5 \
    --region=europe-west8 \
    --redis-version=redis_7_0 \
    --tier=STANDARD_HA \
    --connect-mode=DIRECT_PEERING

# Verificare latenza e utilizzo dell'istanza
gcloud redis instances describe app-cache \
    --region=europe-west8 \
    --format="value(host,port,currentLocationId,memorySizeGb)"

# Configurare Cloud CDN su un backend service (Load Balancer)
gcloud compute backend-services update my-backend-service \
    --enable-cdn \
    --global \
    --cache-mode=CACHE_ALL_STATIC \
    --default-ttl=3600 \
    --max-ttl=86400
```

```yaml
# Configurazione GKE con resource requests/limits per performance prevedibile
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api
          image: europe-west8-docker.pkg.dev/my-project/myapp/api:latest
          resources:
            requests:
              cpu: "250m"      # Garantito dallo scheduler
              memory: "512Mi"
            limits:
              cpu: "1000m"     # Massimo consentito (throttling sopra)
              memory: "1Gi"    # OOM kill se superato
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 20
```

!!! tip "Graviton equivalent su GCP: T2A (Arm) e C3 (custom Intel)"
    Per workload CPU-intensive, le istanze **C3** (Intel Sapphire Rapids) e **T2A** (Arm Ampere Altra) offrono il miglior rapporto prezzo/performance. Le T2A sono ideali per workload containerizzati e web serving. Testare sempre con il proprio workload prima di migrare in produzione.

!!! warning "BigQuery slot allocation"
    Query BigQuery in **on-demand** pagano per byte processato — ottimo per query occasionali. Con query frequenti e pesanti, i **reservations** (slot commitments) danno throughput prevedibile e spesso costano meno. Analizzare il pattern di utilizzo prima di scegliere il modello.

---

## Architecture Center e Strumenti di Review

### Google Cloud Architecture Center

[**Architecture Center**](https://cloud.google.com/architecture) è il repository ufficiale di:
- **Reference architectures** — blueprint pronti per use case comuni (e-commerce, gaming, healthcare, fintech)
- **Best practices guides** — guide approfondite per servizi specifici
- **Solution guides** — pattern per scenari specifici (migrazione, hybrid cloud, data pipelines)

### Framework Assessment

Google mette a disposizione strumenti per condurre assessment formali:

```bash
# Architecture Review — processo consigliato:
# 1. Identificare il workload da revisionare
# 2. Mappare ogni componente ai 6 pilastri
# 3. Per ogni pilastro: identificare gap rispetto alle best practice
# 4. Prioritizzare i gap per impatto e sforzo di remediation
# 5. Creare un improvement plan con milestone e owner

# Lo strumento formale è accessibile via Google Cloud Console:
# Console → Architecture → Framework Assessment
# (disponibile per clienti con supporto Enhanced/Premium)
```

**Well-Architected Partners:** Google ha un programma di partner certificati per condurre architecture review formali — utile per workload mission-critical o revisioni pre-migrazione.

---

## Confronto con AWS WAF e Azure Well-Architected

| Aspetto | GCP Architecture Framework | AWS Well-Architected | Azure Well-Architected |
|---------|---------------------------|---------------------|------------------------|
| **Numero pilastri** | 6 | 6 | 5 + 2 trasversali |
| **Pilastro unico GCP** | System Design (architettura modulare) | — | — |
| **Tool di review** | Console (Enhanced/Premium support) | Gratuito via Console | Azure Advisor + Gratuito |
| **Reference Architectures** | Architecture Center | AWS Architecture Center | Azure Architecture Center |
| **Specializzazioni** | Data/ML, Kubernetes, Enterprise | 10+ Lenses (Serverless, SaaS, ML...) | Industry specifici (FSI, Health) |
| **SRE integration** | Forte (principi SRE Google interni) | Moderata | Moderata |

!!! note "Origini SRE"
    Il pilastro **Reliability** del GCAF è direttamente ispirato al modello **SRE (Site Reliability Engineering)** sviluppato da Google, con concetti come Error Budget, SLO/SLI/SLA, e toil reduction. Google ha pubblicato i [SRE books](https://sre.google/books/) gratuitamente online — lettura consigliata per approfondire.

---

## Best Practices

!!! tip "Iniziare con Reliability e Security"
    Nelle prime fasi di un progetto, prioritizzare **Reliability** (SLO, health checks, multi-zone) e **Security** (IAM least privilege, Secret Manager, VPC design). Sono i pilastri più difficili da aggiungere retroattivamente — molto più semplice disegnarli dall'inizio.

!!! tip "Cost Optimization come processo continuo"
    Non è un'attività una-tantum: allocare un'ora a settimana per rivedere le raccomandazioni di Recommender e i report di Billing Export. Anche piccole ottimizzazioni (rightsizing una VM, cambiare storage class di un bucket) si accumulano nel tempo.

!!! warning "Non trascurare System Design per workload piccoli"
    Anche applicazioni piccole traggono beneficio dai principi di loose coupling e design for failure. Un monolite ben progettato è migliore di microservizi accoppiati male. Il pilastro System Design si applica a tutti i workload, non solo quelli enterprise.

- **Usare Infrastructure as Code** (Terraform o Cloud Deployment Manager) per ogni risorsa — il GCAF considera IaC fondamentale per Operational Excellence e per auditabilità
- **Abilitare Organization Policies** appropriate prima di creare risorse (es. `constraints/iam.disableServiceAccountKeyCreation`, `constraints/compute.requireShieldedVm`)
- **Revisione periodica degli SLO** — gli obiettivi di affidabilità devono evolvere con il business e la maturità del sistema
- **Tagging/labeling sistematico** — essential per Cost Optimization e per correlazione di log/metriche nei pilastri di Observability

---

## Troubleshooting

### Scenario 1 — Architecture review identifica troppi gap, da dove iniziare

**Sintomo:** Dopo un assessment sui 6 pilastri, emergono decine di gap e il team è bloccato su come prioritizzare.

**Causa:** Mancanza di un framework di prioritizzazione — non tutti i gap hanno lo stesso impatto.

**Soluzione:** Prioritizzare usando una matrice Impatto × Urgenza: partire dai gap di **Security** (accesso non autorizzato = rischio immediato) e **Reliability** (downtime = perdita di business). Cost optimization e Performance vengono dopo che il sistema è stabile e sicuro.

```bash
# Audit rapido dei principali rischi Security con SCC
gcloud scc findings list \
    --organization=ORG_ID \
    --filter="state=ACTIVE AND (severity=CRITICAL OR severity=HIGH)" \
    --format="table(category,resourceName,severity,eventTime)" \
    --sort-by="severity"

# Verificare che MFA sia abilitata per tutti gli utenti dell'org
gcloud organizations get-iam-policy ORG_ID \
    --filter="bindings.role:roles/owner" \
    --format="table(bindings.members)"
```

---

### Scenario 2 — Costi GCP fuori controllo senza causa apparente

**Sintomo:** La fattura mensile è aumentata del 40% rispetto al mese precedente senza nuovi deploy evidenti.

**Causa probabile:** Network egress non monitorato, VM o dischi orfani, query BigQuery senza `LIMIT` che scansionano terabyte, o un bug che causa retry loop.

**Soluzione:** Analizzare Billing Export su BigQuery per identificare il servizio con il maggiore incremento. Poi scendere al livello risorsa.

```bash
# Identificare il servizio con maggiore incremento
# (query BigQuery su billing export)
# SELECT service.description,
#        SUM(CASE WHEN DATE(usage_start_time) >= '2026-03-01' THEN cost ELSE 0 END) as current_month,
#        SUM(CASE WHEN DATE(usage_start_time) < '2026-03-01' AND DATE(usage_start_time) >= '2026-02-01' THEN cost ELSE 0 END) as prev_month
# FROM `billing.gcp_billing_export_v1_*`
# GROUP BY 1 ORDER BY current_month DESC LIMIT 10

# Verificare dischi Persistent Disk non collegati a VM
gcloud compute disks list \
    --filter="users:*" \
    --format="table(name,sizeGb,status,zone)" | head -20

# I dischi SENZA users[] sono orfani (la condizione "users:*" include solo quelli con VM)
gcloud compute disks list \
    --format="table(name,sizeGb,status,zone,users)"
```

---

### Scenario 3 — Latenza alta intermittente su Cloud Run

**Sintomo:** Il servizio Cloud Run risponde in < 100ms per la maggior parte delle richieste, ma occasionalmente supera i 2-3 secondi.

**Causa:** Cold start di nuove istanze Cloud Run — il container viene avviato da zero quando non ci sono istanze "calde" disponibili.

**Soluzione:** Configurare `--min-instances` per mantenere almeno 1 istanza sempre calda; ottimizzare il tempo di startup del container (lazy initialization, smaller image).

```bash
# Configurare minimum instances per eliminare cold start
gcloud run services update my-service \
    --region=europe-west8 \
    --min-instances=1 \
    --cpu-boost  # CPU extra durante il cold start

# Verificare la latenza p99 del servizio
gcloud monitoring metrics-scopes list

# Analizzare startup time con Cloud Trace
gcloud trace list --project=my-project \
    --filter="displayName:POST /api/" \
    --limit=20
```

---

### Scenario 4 — GKE pod in CrashLoopBackOff dopo deploy

**Sintomo:** Dopo un rolling update su GKE, i nuovi pod entrano in `CrashLoopBackOff` e il deployment si blocca.

**Causa:** Problema nell'applicazione (OOM, errore di startup, configurazione mancante) o readiness probe troppo aggressiva.

**Soluzione:** Verificare i log del pod, controllare i resource limits, e verificare che le environment variables e i secrets siano configurati correttamente.

```bash
# Diagnostica rapida del pod in crash
kubectl describe pod <pod-name> -n <namespace>

# Visualizzare i log del pod che crasha
kubectl logs <pod-name> -n <namespace> --previous

# Verificare se è un problema di OOM (Out Of Memory)
kubectl get events -n <namespace> --sort-by='.metadata.creationTimestamp' | grep OOM

# Verificare i resource limits applicati
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].resources}'

# Rollback immediato al deployment precedente
kubectl rollout undo deployment/my-deployment -n <namespace>

# Verificare lo stato del rollback
kubectl rollout status deployment/my-deployment -n <namespace>
```

---

## Relazioni

??? info "AWS Well-Architected Framework — Confronto"
    Il GCAF e l'AWS WAF condividono la stessa struttura a 6 pilastri con obiettivi analoghi. La differenza principale è che GCP separa **System Design** come pilastro autonomo, mentre AWS include questi principi trasversalmente. Il GCP Architecture Framework ha una forte impronta **SRE** (error budget, SLO) derivante dalle pratiche interne di Google.

    **Approfondimento →** [AWS Well-Architected Framework](../../aws/fondamentali/well-architected.md)

??? info "Azure Well-Architected Framework — Confronto"
    Azure WAF ha 5 pilastri (Reliability, Security, Cost Optimization, Operational Excellence, Performance Efficiency) più 2 trasversali (Sustainability e Application Design). L'Assessment Tool di Azure è gratuito e integrato in Azure Portal, mentre il GCP tool è disponibile per clienti con supporto Enhanced/Premium.

    **Approfondimento →** [Azure Well-Architected Framework](../../azure/fondamentali/well-architected.md)

??? info "Shared Responsibility Model GCP"
    Il GCAF presuppone la comprensione del modello di responsabilità condivisa GCP: Google gestisce sicurezza e affidabilità dell'infrastruttura cloud, il cliente è responsabile della corretta configurazione dei servizi e dei propri dati.

    **Approfondimento →** [Shared Responsibility GCP](shared-responsibility.md)

---

## Riferimenti

- [Google Cloud Architecture Framework](https://cloud.google.com/architecture/framework)
- [Google Cloud Architecture Center](https://cloud.google.com/architecture)
- [SRE Books (Google)](https://sre.google/books/)
- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)
- [Cloud Billing Documentation](https://cloud.google.com/billing/docs)
- [Cloud Monitoring SLOs](https://cloud.google.com/monitoring/service-monitoring)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [GCP Reference Architectures](https://cloud.google.com/architecture#reference-architectures)
