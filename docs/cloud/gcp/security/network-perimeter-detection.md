---
title: "Protezione di Rete e Detection su GCP"
slug: network-perimeter-detection
category: cloud/gcp/security
tags: [gcp, cloud-armor, vpc-service-controls, security-command-center, waf, ddos, data-exfiltration, organization-policy, security]
search_keywords: [Cloud Armor, GCP WAF, Google Cloud Armor, VPC Service Controls, VPC-SC, service perimeter, data exfiltration GCP, Security Command Center, SCC, Cloud Asset Inventory, Adaptive Protection, OWASP CRS GCP, rate limiting GCP, DDoS protection GCP, Global Load Balancer security, network perimeter GCP, perimetro di rete GCP, organization policy security, restrict public IP, uniform bucket-level access, access context manager, VPC-SC dry run, security posture GCP, misconfigurazione GCP, CSPM GCP]
parent: cloud/gcp/security/_index
related: [cloud/gcp/security/kms-secret-manager, cloud/gcp/iam/iam-service-accounts, cloud/gcp/networking/vpc, cloud/aws/security/network-security, cloud/aws/security/compliance-audit]
official_docs: https://cloud.google.com/armor/docs
status: complete
difficulty: advanced
last_updated: 2026-10-03
---

# Protezione di Rete e Detection su GCP

## Panoramica

GCP separa la protezione a livello di rete/perimetro in tre servizi complementari che rispondono a domande diverse: **Cloud Armor** filtra il traffico L7 in ingresso verso i servizi dietro un Global Load Balancer (è il WAF/anti-DDoS di GCP); **VPC Service Controls** crea un perimetro a livello di API che impedisce l'esfiltrazione di dati anche quando le credenziali IAM sono valide; **Security Command Center** è il layer di detection/CSPM (Cloud Security Posture Management, verifica continua delle misconfigurazioni) che aggrega misconfigurazioni, vulnerabilità e minacce attive su tutto l'estate GCP.

**Quando servono:**
- Servizi pubblici (API, web app) dietro Global External Load Balancer esposti a traffico internet non fidato → Cloud Armor
- Dati sensibili (PII, dati finanziari) in BigQuery/GCS che non devono uscire dal perimetro aziendale anche se un insider ha credenziali IAM valide → VPC Service Controls
- Necessità di visibilità centralizzata su misconfigurazioni, vulnerabilità e minacce attraverso decine/centinaia di project → Security Command Center

**Quando NON servono:**
- Traffico interno tra microservizi nella stessa VPC, già fidato → non serve Cloud Armor (usare invece Firewall Rules o service mesh, vedi [VPC](../networking/vpc.md))
- Singolo project con pochi servizi, nessun requisito di compliance su data exfiltration → VPC-SC aggiunge complessità operativa non giustificata
- Organizzazioni che vogliono solo IAM corretto senza detection continua → Security Command Center Standard (gratuito) basta per i controlli base; Premium è un costo aggiuntivo da giustificare con requisiti reali

---

## Concetti Chiave

### Cloud Armor — Modello di Protezione

Cloud Armor opera a livello di **Load Balancer**, non di singola VM o servizio: le regole si applicano a un **Security Policy** collegata al backend service del Global External Application Load Balancer (o Classic LB).

| Componente | Cosa fa |
|---|---|
| **Security Policy** | Contenitore di regole, associato a uno o più backend service |
| **Rule** | Condizione (match CEL su IP, header, path, geolocalizzazione) + azione (`allow`, `deny(403)`, `redirect`, `throttle`) + priorità numerica |
| **Preconfigured WAF Rules** | Regole pronte basate su OWASP ModSecurity Core Rule Set (CRS) — SQLi, XSS, RCE, protocol attack |
| **Adaptive Protection** | Modello ML che rileva pattern di attacco L7 (DDoS applicativo) e genera automaticamente regole di mitigazione suggerite |

!!! warning "Le regole si valutano in ordine di priorità, non di specificità"
    Cloud Armor valuta le regole in ordine di **priorità numerica crescente** (0 = più alta) e si ferma alla prima che matcha. Una regola generica con numero di priorità più piccolo di una regola specifica (quindi valutata prima) la rende irraggiungibile — causa comune di "la regola non si applica".

### Preconfigured WAF Rules — Sensitivity Level

Le regole OWASP CRS (Core Rule Set, set open-source di firme ModSecurity per attacchi web) hanno un **sensitivity level** (1-4) che bilancia copertura contro falsi positivi: ogni livello include le firme dei livelli inferiori, quindi salendo si aggiungono firme più aggressive.

```
Livello 1 → poche firme ad alta confidenza, minimo rischio di falsi positivi (punto di partenza)
Livello 2 → copertura maggiore, qualche falso positivo da tarare
Livello 3 → protezione alta, tuning necessario
Livello 4 → massima copertura, più falsi positivi (richiede tuning attento)
```

!!! tip "Preview mode prima di enforcing"
    Ogni regola Cloud Armor supporta `preview: true` — logga i match senza bloccare. Usarlo sempre prima di attivare `deny` in produzione, specialmente con le preconfigured WAF rules: un sensitivity level troppo aggressivo blocca traffico legittimo (es. payload JSON con pattern simili a SQLi).

### Rate Limiting e Adaptive Protection

- **Rate-based ban**: conta le richieste per chiave (IP, header custom, cookie) in una finestra temporale e banna chi supera la soglia per un periodo configurabile.
- **Throttle**: come il rate-based ban ma invece di bloccare completamente limita il throughput.
- **Adaptive Protection**: analizza il traffico in tempo reale, rileva anomalie compatibili con DDoS L7 (richieste distribuite su molti IP con pattern comune), e genera un **alert con una regola suggerita** — non blocca automaticamente, l'attivazione della regola suggerita resta una decisione umana (o automatizzabile via API).

### VPC Service Controls — Il Problema che Risolve

IAM risponde a "chi può chiamare questa API", ma non impedisce che un principal autorizzato copi dati da un progetto sensibile verso un bucket pubblico o un progetto esterno. **VPC Service Controls (VPC-SC)** aggiunge un controllo ortogonale a livello di rete/API: un **perimetro di servizio** attorno a un gruppo di project, dentro cui le chiamate API a servizi supportati (BigQuery, GCS, BigTable, ecc.) sono permesse solo se l'origine della richiesta è anch'essa dentro il perimetro (o esplicitamente autorizzata via Access Level).

!!! warning "VPC-SC non sostituisce IAM, lo affianca"
    Un utente con `roles/bigquery.admin` valido viene comunque bloccato da VPC-SC se tenta di esportare dati verso un progetto fuori perimetro. I due controlli sono **AND**, non OR: serve sia il permesso IAM sia il rispetto del perimetro. Questo è il concetto più spesso frainteso — VPC-SC non è "IAM più granulare", è un livello di difesa indipendente contro l'exfiltration.

### VPC-SC — Componenti

| Componente | Funzione |
|---|---|
| **Service Perimeter** | Il confine: un insieme di project + un insieme di servizi GCP regolati (restricted services) |
| **Access Level** | Eccezione al perimetro basata su identità, IP range, o device policy (via Access Context Manager) — permette accesso da fuori in casi controllati |
| **Ingress/Egress Rule** | Regole granulari che permettono traffico specifico tra perimetri diversi o verso l'esterno |
| **Dry-run mode** | Il perimetro logga le violazioni senza bloccare — passo obbligatorio prima dell'enforcing |

```
Perimetro "prod-data"
├── Project: prod-bigquery
├── Project: prod-gcs
├── Restricted services: bigquery.googleapis.com, storage.googleapis.com
└── Access Level: "office-network" (IP range ufficio + device policy approvata)

Richiesta da fuori il perimetro senza Access Level → BLOCCATA (anche con IAM valido)
Richiesta da dentro il perimetro → permessa secondo IAM
Richiesta da IP ufficio (Access Level) → permessa anche se il client è fuori perimetro
```

### Security Command Center — Standard vs Premium

| Caratteristica | Standard (gratuito) | Premium (a pagamento) |
|---|---|---|
| Asset inventory | Sì, base | Sì, completo con storico |
| Misconfigurazioni (Security Health Analytics) | Set limitato di detector | Set completo, incluso CIS Benchmark GCP |
| Vulnerability scanning | No | Sì (Web Security Scanner, container vulnerabilities) |
| Threat detection (Event Threat Detection) | No | Sì (crypto-mining, brute force, anomalie IAM) |
| Compliance reports | No | Sì (CIS, PCI-DSS, NIST mapping automatico) |
| Integrazione Cloud Asset Inventory | Sì | Sì, con query avanzate |

!!! tip "Standard copre già le basi più comuni"
    Molti dei finding più critici (bucket pubblici, firewall troppo permissivi, SA con `roles/editor`) sono coperti anche da SCC Standard tramite Security Health Analytics di base. Valutare Premium quando serve detection di minacce attive o compliance reporting automatico, non solo per avere "più findings".

### Organization Policies Rilevanti per la Sicurezza di Rete

Le Organization Policy (vedi anche [IAM e Service Account](../iam/iam-service-accounts.md)) impongono vincoli preventivi indipendenti da IAM, applicabili a Organization/Folder/Project:

| Constraint | Cosa impone |
|---|---|
| `compute.vmExternalIpAccess` | Vieta IP pubblici sulle VM Compute Engine |
| `compute.restrictVpcPeering` | Limita il VPC Peering a progetti/organizzazioni approvate |
| `compute.restrictLoadBalancerCreationForTypes` | Permette solo tipi di Load Balancer approvati (es. solo interni) |
| `storage.publicAccessPrevention` | Vieta bucket GCS pubblicamente accessibili |
| `storage.uniformBucketLevelAccess` | Forza ACL uniformi a livello bucket (vieta ACL per singolo oggetto) |
| `iam.allowedPolicyMemberDomains` | Vieta `allUsers`/`allAuthenticatedUsers` nelle policy IAM |

---

## Architettura / Come Funziona

### Cloud Armor — Flusso di una Richiesta

```
Client Internet
      │
      ▼
Global External Application Load Balancer
      │
      ▼
Cloud Armor Security Policy (valutata PRIMA del backend)
      │
      ├── Match regola priorità 1000 (deny IP range malevolo)? → 403, STOP
      ├── Match preconfigured WAF rule (SQLi pattern)? → 403 (o preview: solo log), STOP
      ├── Match rate-based ban (soglia superata)? → throttle/ban, STOP
      ├── Adaptive Protection rileva anomalia? → alert (non blocca di default)
      └── Nessun match → passa al backend
                │
                ▼
         Backend Service (Cloud Run, GKE Ingress, Compute Engine MIG)
```

Il punto critico: Cloud Armor valuta **prima** che il traffico raggiunga il backend — un attacco bloccato non consuma risorse applicative, a differenza di un WAF applicativo (es. middleware in-app).

### VPC-SC — Flusso di una Chiamata API

```
Client (utente o service account, IAM valido)
      │
      │ Chiamata API (es. bigquery.jobs.query)
      ▼
Controllo IAM: il principal ha il permesso? ──────── no → 403 PERMISSION_DENIED
      │ sì
      ▼
Controllo VPC-SC: l'origine della chiamata è dentro
il perimetro del progetto target, o copre un Access Level? ──── no → 403 VPC-SC violation
      │ sì
      ▼
Richiesta eseguita
```

Entrambi i controlli devono passare. Il log di una violazione VPC-SC (visibile in Cloud Logging con `protoPayload.metadata.@type` contenente `VpcServiceControlAuditMetadata`) riporta il perimetro violato e il servizio bloccato — fondamentale per il debug (vedi Troubleshooting).

---

## Configurazione & Pratica

### Cloud Armor — Security Policy Base

```bash
# ── CREARE LA SECURITY POLICY ────────────────────────────────────────
gcloud compute security-policies create prod-waf-policy \
    --description="WAF policy per servizi pubblici prod"

# ── REGOLA: BLOCCARE UN RANGE IP NOTO MALEVOLO ───────────────────────
gcloud compute security-policies rules create 1000 \
    --security-policy=prod-waf-policy \
    --expression="origin.ip in ['198.51.100.0/24', '203.0.113.0/24']" \
    --action=deny-403 \
    --description="Blocca range IP malevoli noti"

# ── REGOLA: PRECONFIGURED WAF RULE (SQLi) IN PREVIEW ─────────────────
# Sempre iniziare in preview per misurare i falsi positivi
gcloud compute security-policies rules create 2000 \
    --security-policy=prod-waf-policy \
    --expression="evaluatePreconfiguredExpr('sqli-v33-stable', ['owasp-crs-v030301-id942100-sqli'])" \
    --action=deny-403 \
    --preview \
    --description="SQLi OWASP CRS - PREVIEW"

# ── REGOLA: RATE LIMITING PER IP ─────────────────────────────────────
gcloud compute security-policies rules create 3000 \
    --security-policy=prod-waf-policy \
    --expression="true" \
    --action=throttle \
    --rate-limit-threshold-count=100 \
    --rate-limit-threshold-interval-sec=60 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP \
    --description="Max 100 req/min per IP"

# ── ABILITARE ADAPTIVE PROTECTION ────────────────────────────────────
gcloud compute security-policies update prod-waf-policy \
    --enable-layer7-ddos-defense

# ── ASSOCIARE LA POLICY AL BACKEND SERVICE ───────────────────────────
gcloud compute backend-services update my-backend-service \
    --security-policy=prod-waf-policy \
    --global

# Listare le regole attive e il loro stato (enforce vs preview)
gcloud compute security-policies rules list \
    --security-policy=prod-waf-policy \
    --format="table(priority, action, preview, description)"
```

### VPC Service Controls — Setup Perimetro

```bash
# ── CREARE UN ACCESS POLICY (prerequisito, uno per Organization) ─────
gcloud access-context-manager policies create \
    --organization=ORGANIZATION_ID \
    --title="Org Access Policy"

# Ottenere l'ID della policy creata
gcloud access-context-manager policies list --organization=ORGANIZATION_ID

# ── CREARE UN ACCESS LEVEL (eccezione per rete ufficio) ──────────────
cat > /tmp/access-level.yaml << 'EOF'
- ipSubnetworks:
  - "203.0.113.0/24"
EOF
gcloud access-context-manager levels create office_network \
    --policy=ACCESS_POLICY_ID \
    --title="Office Network" \
    --basic-level-spec=/tmp/access-level.yaml

# ── CREARE IL PERIMETRO IN DRY-RUN (OBBLIGATORIO PRIMA DELL'ENFORCING) ─
gcloud access-context-manager perimeters create prod_data_perimeter \
    --policy=ACCESS_POLICY_ID \
    --title="Prod Data Perimeter" \
    --resources=projects/PROJECT_NUMBER_BIGQUERY,projects/PROJECT_NUMBER_GCS \
    --restricted-services=bigquery.googleapis.com,storage.googleapis.com \
    --access-levels=office_network \
    --perimeter-type=regular \
    --dry-run

# ── VERIFICARE LE VIOLAZIONI LOGGATE IN DRY-RUN (prima di enforce) ───
gcloud logging read \
    'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"' \
    --project=PROJECT_ID_BIGQUERY \
    --limit=50 \
    --format=json

# ── PROMUOVERE DA DRY-RUN A ENFORCED (dopo aver validato zero falsi positivi) ─
gcloud access-context-manager perimeters dry-run enforce prod_data_perimeter \
    --policy=ACCESS_POLICY_ID

# Verificare lo stato del perimetro
gcloud access-context-manager perimeters describe prod_data_perimeter \
    --policy=ACCESS_POLICY_ID
```

### Security Command Center — Query Findings

```bash
# ── ABILITARE SCC (richiede roles/securitycenter.admin a livello Org) ─
gcloud scc settings describe --organization=ORGANIZATION_ID

# ── LISTARE FINDING ATTIVI AD ALTA SEVERITÀ ──────────────────────────
gcloud scc findings list ORGANIZATION_ID \
    --filter='severity="HIGH" AND state="ACTIVE"' \
    --format="table(finding.category, finding.resourceName, finding.severity)"

# ── FINDING SPECIFICI SU BUCKET PUBBLICI ─────────────────────────────
gcloud scc findings list ORGANIZATION_ID \
    --filter='category="PUBLIC_BUCKET_ACL" AND state="ACTIVE"'

# ── MUTARE LO STATO DI UN FINDING (dopo remediation) ─────────────────
gcloud scc findings update FINDING_ID \
    --organization=ORGANIZATION_ID \
    --source=SOURCE_ID \
    --state=INACTIVE

# ── ESPORTARE FINDING VERSO BIGQUERY (per dashboard custom) ──────────
gcloud scc bqexports create prod-findings-export \
    --organization=ORGANIZATION_ID \
    --dataset=projects/my-project-id/datasets/scc_findings \
    --filter='severity="HIGH" OR severity="CRITICAL"'
```

### Organization Policy — Enforcement di Rete

```bash
# Vietare IP pubblici su tutte le VM dell'organizzazione
gcloud org-policies set-policy - << 'EOF'
name: organizations/ORGANIZATION_ID/policies/compute.vmExternalIpAccess
spec:
  rules:
  - denyAll: true
EOF

# Vietare bucket GCS pubblici
gcloud org-policies set-policy - << 'EOF'
name: organizations/ORGANIZATION_ID/policies/storage.publicAccessPrevention
spec:
  rules:
  - enforce: true
EOF
```

---

## Best Practices

!!! warning "Mai attivare Cloud Armor WAF rules direttamente in enforcing su produzione"
    Le preconfigured WAF rules (OWASP CRS) generano falsi positivi su traffico legittimo con payload JSON/XML complessi. Attivare sempre con `--preview` per almeno 1-2 settimane, analizzare i log, calibrare il sensitivity level, e solo dopo passare a `deny`.

!!! tip "VPC-SC dry-run è obbligatorio, non opzionale"
    Un perimetro VPC-SC enforced senza passaggio da dry-run blocca tipicamente integrazioni legittime non previste (pipeline CI/CD, servizi SaaS terzi che leggono da BigQuery). Il dry-run per 1-4 settimane con analisi dei log è lo step che distingue un rollout pulito da un incidente di servizio.

1. Associare Cloud Armor a tutti i backend service esposti via Global Load Balancer, anche quelli "interni" se raggiungibili da internet
2. Usare Adaptive Protection in ambienti ad alto traffico pubblico — la detection ML coglie pattern che regole statiche non intercettano
3. Costruire i perimetri VPC-SC per dominio di dati (es. un perimetro per dati PII, uno per dati finanziari), non un unico perimetro per tutta l'organizzazione — riduce il blast radius di un Access Level troppo permissivo
4. Collegare SCC Premium a un sistema di ticketing/SIEM esterno (via BigQuery export o Pub/Sub) invece di monitorare solo la console
5. Rivedere periodicamente gli Access Level VPC-SC: un range IP ufficio obsoleto (es. dopo un trasloco) diventa un buco silenzioso nel perimetro
6. Applicare le Organization Policy di rete (`vmExternalIpAccess`, `publicAccessPrevention`) a livello Organization, non singolo project — previene la ricomparsa del problema in nuovi project
7. Testare le regole Cloud Armor con traffico sintetico prima del cutover (es. `curl` con header/path che replicano pattern di attacco noti)

---

## Troubleshooting

### Scenario 1 — Regola Cloud Armor non si applica nonostante il match atteso

**Sintomo:** Una richiesta che dovrebbe matchare una regola `deny` passa comunque al backend.

**Causa:** Una regola con priorità numerica più bassa (valutata prima) matcha genericamente e permette (`allow`) il traffico prima che la regola specifica venga valutata — Cloud Armor si ferma al primo match.

**Soluzione:**
```bash
# Verificare l'ordine di valutazione (priorità crescente = valutata prima)
gcloud compute security-policies rules list \
    --security-policy=prod-waf-policy \
    --format="table(priority, match.expr.expression, action)" \
    --sort-by=priority

# Spostare la regola specifica a priorità più bassa (es. da 5000 a 500)
gcloud compute security-policies rules update 5000 \
    --security-policy=prod-waf-policy \
    --new-priority=500
```

### Scenario 2 — VPC-SC blocca una chiamata API legittima

**Sintomo:** Un servizio autorizzato via IAM riceve `403 Request is prohibited by organization's policy` su una chiamata BigQuery/GCS.

**Causa:** Il chiamante (utente, SA, o pipeline CI/CD) opera da un'origine di rete fuori dal perimetro e non copre nessun Access Level configurato.

**Soluzione:**
```bash
# 1. Trovare il log della violazione — riporta perimetro e servizio coinvolti
gcloud logging read \
    'protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlAuditMetadata"' \
    --project=PROJECT_ID \
    --limit=10 --format=json

# 2. Identificare l'IP/identità sorgente dal campo callerIp o principalEmail nel log

# 3a. Se l'origine è legittima e ricorrente (es. pipeline CI/CD):
#     aggiungere un Access Level dedicato o una Ingress Rule
gcloud access-context-manager perimeters update prod_data_perimeter \
    --policy=ACCESS_POLICY_ID \
    --add-access-levels=ci_cd_pipeline

# 3b. Se l'origine deve restare dentro un altro perimetro:
#     usare una Ingress/Egress Rule tra i due perimetri invece di un Access Level globale
```

### Scenario 3 — Security Command Center non mostra finding attesi

**Sintomo:** Una misconfigurazione nota (es. bucket pubblico) non appare tra i finding SCC.

**Causa:** SCC Standard non include il detector specifico (riservato a Premium), oppure l'asset non è ancora stato scansionato (latenza di scan, tipicamente alcune ore).

**Soluzione:**
```bash
# Verificare il tier attivo
gcloud scc settings describe --organization=ORGANIZATION_ID

# Verificare manualmente la risorsa mentre si attende lo scan
gcloud storage buckets describe gs://my-bucket --format="value(iamConfiguration.publicAccessPrevention)"

# Forzare un refresh di Cloud Asset Inventory (non rigenera i finding SCC,
# ma conferma che l'asset è visibile al sistema)
gcloud asset search-all-resources \
    --scope="projects/my-project-id" \
    --query="name:my-bucket"
```

### Scenario 4 — Adaptive Protection genera troppi alert senza azione chiara

**Sintomo:** Il dashboard Adaptive Protection segnala anomalie ricorrenti ma nessuna regola viene suggerita o le regole suggerite sembrano troppo generiche.

**Causa:** Il modello ML richiede un volume minimo di traffico storico (tipicamente alcune settimane) per costruire una baseline affidabile; su backend a basso traffico le anomalie rilevate sono spesso falsi positivi statistici.

**Soluzione:**
```bash
# Verificare da quanto tempo è attivo Adaptive Protection sul backend
gcloud compute security-policies describe prod-waf-policy \
    --format="value(adaptiveProtectionConfig)"

# Nel frattempo, affidarsi a rate limiting esplicito (soglie statiche)
# come rete di sicurezza mentre la baseline ML matura
gcloud compute security-policies rules list \
    --security-policy=prod-waf-policy \
    --filter="action:throttle OR action:rate_based_ban"
```

### PERMISSION_DENIED vs VPC-SC violation — distinguere le due cause

1. Leggere il messaggio di errore completo: `PERMISSION_DENIED` puro è IAM; `Request is prohibited by organization's policy` è VPC-SC
2. Un errore IAM si risolve con un binding (`add-iam-policy-binding`); un errore VPC-SC richiede un Access Level o una Ingress/Egress Rule — un binding IAM aggiuntivo non ha alcun effetto
3. Verificare sempre il log `VpcServiceControlAuditMetadata` prima di modificare permessi IAM per un errore che in realtà è di perimetro

---

## Relazioni

??? info "VPC e Firewall Rules"
    Cloud Armor e VPC-SC operano a livello applicativo/API; il filtraggio di rete L3/L4 tra risorse nella stessa VPC resta compito delle Firewall Rules VPC.

    **Approfondimento completo →** [VPC GCP](../networking/vpc.md)

??? info "IAM, Service Account e Organization Policy"
    VPC-SC e le Organization Policy di rete si affiancano a IAM come controllo indipendente (AND logico, non sostitutivo). I constraint `compute.*` e `storage.*` qui descritti usano lo stesso meccanismo di Org Policy illustrato per IAM.

    **Approfondimento completo →** [GCP IAM e Service Account](../iam/iam-service-accounts.md)

??? info "Cloud KMS e Secret Manager"
    La protezione del perimetro di rete (questo file) e la protezione dei dati a riposo/dei secret sono controlli complementari: VPC-SC impedisce l'esfiltrazione, KMS/Secret Manager proteggono la confidenzialità di chiavi e credenziali.

    **Approfondimento completo →** [Cloud KMS e Secret Manager](kms-secret-manager.md)

??? info "AWS — Network Security e Compliance Audit"
    AWS espone concetti equivalenti con nomi diversi: AWS WAF + Shield (equivalente di Cloud Armor), AWS Security Hub (equivalente di Security Command Center). Non esiste un equivalente diretto 1:1 di VPC Service Controls in AWS — il controllo più vicino combina VPC Endpoint Policies e SCP (Service Control Policies) a livello Organization.

    **Approfondimento completo →** [AWS Network Security](../../aws/security/network-security.md) · [AWS Compliance & Audit](../../aws/security/compliance-audit.md)

---

## Riferimenti

- [Cloud Armor Overview](https://cloud.google.com/armor/docs)
- [Cloud Armor — Preconfigured WAF Rules](https://cloud.google.com/armor/docs/waf-rules)
- [Cloud Armor — Adaptive Protection](https://cloud.google.com/armor/docs/adaptive-protection-overview)
- [VPC Service Controls Overview](https://cloud.google.com/vpc-service-controls/docs/overview)
- [VPC Service Controls — Access Levels](https://cloud.google.com/access-context-manager/docs/overview)
- [Security Command Center Overview](https://cloud.google.com/security-command-center/docs/security-command-center-overview)
- [SCC — Standard vs Premium](https://cloud.google.com/security-command-center/docs/security-command-center-service-tiers)
- [Organization Policy Service](https://cloud.google.com/resource-manager/docs/organization-policy/overview)
- [Cloud Asset Inventory](https://cloud.google.com/asset-inventory/docs/overview)
