---
title: "Cloud Run"
slug: cloud-run
category: cloud/gcp/compute
tags: [gcp, serverless, containers, cloud-run, fully-managed, scale-to-zero]
search_keywords: [Cloud Run, serverless container GCP, container serverless Google, scale-to-zero GCP, Cloud Run fully managed, Cloud Run jobs, Cloud Run Functions, gcloud run deploy, revision Cloud Run, traffic splitting Cloud Run, Cloud Run VPC, Cloud Run networking, Cloud Run autoscaling, concorrenza Cloud Run, cold start Cloud Run, Cloud Run min instances, Cloud Run max instances, Cloud Run HTTPS, Cloud Run ingress, Cloud Run egress, Cloud Run IAM, Cloud Run service account, Cloud Run invoker, Cloud Run authentication, container serverless vs Lambda, Fargate GCP alternativa, serverless container Google Cloud, Cloud Run YAML, Cloud Run service definition, Cloud Run CPU always-on, Cloud Run CPU request-based, Cloud Run secrets, Cloud Run env vars, Cloud Run mount volume, Cloud Run Cloud SQL, Cloud Run direct VPC egress, Cloud Run private, Cloud Run internal]
parent: cloud/gcp/compute/_index
related: [cloud/gcp/containers/gke, cloud/gcp/fondamentali/panoramica]
official_docs: https://cloud.google.com/run/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-25
---

# Cloud Run

## Panoramica

Cloud Run è il servizio **serverless per container** di Google Cloud: deploy un'immagine container, Cloud Run la esegue su infrastruttura fully managed gestendo automaticamente scalabilità, SSL, load balancing e disponibilità. Non esistono cluster, nodi o VM da gestire.

Il modello operativo è request-driven: i container ricevono richieste HTTP/gRPC, Cloud Run scala le istanze automaticamente in base al traffico, e — per default — scala a **zero istanze** quando non ci sono richieste in arrivo (scale-to-zero), eliminando i costi in idle.

**Quando usare Cloud Run:**
- Servizi HTTP/gRPC stateless (API, microservizi, webhook, frontend SSR)
- Workload con traffico intermittente o imprevedibile — scala da 0 a N istanze in secondi
- Team che vogliono containerizzare senza gestire Kubernetes
- Migrazione di applicazioni containerizzate esistenti senza riscrivere
- Esecuzione di job asincroni o batch a tempo determinato (Cloud Run Jobs)

**Quando scegliere alternative:**
- Workload con stato persistente su disco locale → **GKE** (volume PersistentVolumeClaim)
- Necessità di DaemonSet, sidecar avanzati, o Service Mesh → **GKE**
- Latenza ultra-bassa senza cold start accettabile → GKE con min replicas sempre attive
- Protocolli non HTTP (TCP raw, UDP, WebSocket long-lived senza HTTP) → **GKE**

**Le tre forme di Cloud Run:**

| Prodotto | Use case | Trigger | Stato |
|---|---|---|---|
| **Cloud Run Services** | Servizi HTTP/gRPC continui | Richieste HTTP | GA |
| **Cloud Run Jobs** | Esecuzione batch a completamento | Manuale / schedule / evento | GA |
| **Cloud Run Functions** | Funzioni event-driven (evoluzione di Cloud Functions) | HTTP, Pub/Sub, Eventarc | GA |

---

## Architettura / Come Funziona

### Lifecycle di una Richiesta

```
Client
  │
  ▼
Cloud Load Balancer (Google-managed, SSL termination, anycast IP)
  │
  ▼
Cloud Run Frontend (routing per revision e traffic split)
  │
  ├── Istanza già calda → inoltro diretto alla porta container (default 8080)
  │
  └── Nessuna istanza → cold start
        ├── Scarica immagine dal registry (Artifact Registry)
        ├── Avvia container (entrypoint / CMD)
        ├── Attende che la porta sia in ascolto
        └── Inoltro richiesta (timeout di avvio: default 4 min, max 60 min)
```

Il container **deve** avviare un server HTTP sulla porta configurata (default `PORT=8080`, variabile iniettata automaticamente). Cloud Run invia richieste a quella porta e considera il container pronto quando la porta è in ascolto.

### Revision e Traffic Splitting

Ogni deploy crea una nuova **Revision** — uno snapshot immutabile dell'immagine + configurazione. Il traffico viene instradato verso le Revision tramite regole percentuali.

```
Cloud Run Service "my-api"
├── Revision my-api-00042  → 90% del traffico   ← versione stabile
├── Revision my-api-00043  → 10% del traffico   ← canary
└── Revision my-api-00044  → 0%  (latest, non ancora promossa)
```

Questo permette deployment canary, A/B testing e rollback istantaneo — senza downtime.

### Modello di Concorrenza

A differenza di Lambda/Functions (1 richiesta per istanza per default), Cloud Run supporta **concorrenza multipla**: ogni istanza può gestire più richieste simultaneamente.

```
Istanza Cloud Run (es. 1 vCPU, 512 MiB)
├── Richiesta 1 (in elaborazione)
├── Richiesta 2 (in elaborazione)
├── Richiesta 3 (in elaborazione)
└── ... fino a maxConcurrentRequests (default: 80, max: 1000)
```

Quando tutte le istanze sono sature al 100% della concorrenza configurata, Cloud Run avvia nuove istanze. La formula per stimare il numero di istanze:

```
istanze_necessarie = ceil(RPS / (concurrency * requestsPerSecond_per_vCPU))
```

!!! warning "Concorrenza e thread-safety"
    Se la tua applicazione non è thread-safe (es. variabili globali mutabili), abbassare `maxConcurrentRequests` a 1 — ogni istanza gestirà una sola richiesta alla volta, come una Lambda. Questo aumenta i costi ma garantisce isolamento.

### CPU Allocation

Cloud Run offre due modalità di allocazione CPU:

| Modalità | Quando la CPU è attiva | Costo | Use case |
|---|---|---|---|
| **CPU throttled** (default) | Solo durante richieste HTTP | Più basso | Servizi HTTP stateless standard |
| **CPU always-on** | Sempre (anche tra richieste) | Più alto | Background tasks, caching in memoria, websocket |

Con CPU throttled, i processi in background (goroutine, thread, timer) vengono **congelati** tra una richiesta e l'altra — non eseguono istruzioni finché non arriva una nuova richiesta.

---

## Configurazione & Pratica

### Deploy Base

```bash
# Deploy di un'immagine esistente su Artifact Registry
gcloud run deploy my-service \
    --image=europe-west8-docker.pkg.dev/my-project/my-repo/my-app:latest \
    --region=europe-west8 \
    --platform=managed

# Deploy con accesso pubblico (unauthenticated)
gcloud run deploy my-service \
    --image=europe-west8-docker.pkg.dev/my-project/my-repo/my-app:latest \
    --region=europe-west8 \
    --allow-unauthenticated

# Deploy con variabili d'ambiente e risorse
gcloud run deploy my-service \
    --image=europe-west8-docker.pkg.dev/my-project/my-repo/my-app:latest \
    --region=europe-west8 \
    --cpu=2 \
    --memory=1Gi \
    --concurrency=80 \
    --min-instances=1 \
    --max-instances=100 \
    --timeout=300 \
    --set-env-vars="ENV=production,LOG_LEVEL=info" \
    --service-account=my-app-sa@my-project.iam.gserviceaccount.com

# Verificare il deploy
gcloud run services describe my-service --region=europe-west8
gcloud run services list --region=europe-west8
```

### Service Definition YAML

Cloud Run supporta deploy dichiarativi tramite YAML (formato Knative compatible):

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: my-service
  annotations:
    run.googleapis.com/ingress: all          # all | internal | internal-and-cloud-load-balancing
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "50"
        run.googleapis.com/cpu-throttling: "false"       # CPU always-on
        run.googleapis.com/execution-environment: gen2   # 2a generazione sandbox
    spec:
      serviceAccountName: my-app-sa@my-project.iam.gserviceaccount.com
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
      - image: europe-west8-docker.pkg.dev/my-project/my-repo/my-app:latest
        ports:
        - name: http1
          containerPort: 8080
        resources:
          limits:
            cpu: "2"
            memory: 1Gi
        env:
        - name: ENV
          value: production
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              key: latest               # versione del secret
              name: db-password         # nome del secret in Secret Manager
        startupProbe:
          httpGet:
            path: /healthz
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /healthz
          periodSeconds: 30
```

```bash
# Deploy tramite YAML
gcloud run services replace cloud-run-service.yaml --region=europe-west8
```

### Traffic Splitting e Canary

```bash
# Deploy nuova revision SENZA spostare traffico (tag per test diretto)
gcloud run deploy my-service \
    --image=europe-west8-docker.pkg.dev/my-project/my-repo/my-app:v2 \
    --region=europe-west8 \
    --no-traffic \
    --tag=canary

# Testare la revision canary direttamente via URL tag
# URL pattern: https://canary---my-service-xxxx-xx.a.run.app

# Spostare 10% del traffico alla revision canary
gcloud run services update-traffic my-service \
    --region=europe-west8 \
    --to-tags=canary=10

# Promuovere al 100% (rollout completo)
gcloud run services update-traffic my-service \
    --region=europe-west8 \
    --to-latest

# Rollback alla revision precedente
gcloud run services update-traffic my-service \
    --region=europe-west8 \
    --to-revisions=my-service-00041=100

# Verificare la distribuzione traffico corrente
gcloud run services describe my-service \
    --region=europe-west8 \
    --format="value(spec.traffic)"
```

### Cloud Run Jobs

I **Cloud Run Jobs** eseguono container fino al completamento (non server HTTP):

```bash
# Creare un job
gcloud run jobs create my-batch-job \
    --image=europe-west8-docker.pkg.dev/my-project/my-repo/batch-worker:latest \
    --region=europe-west8 \
    --tasks=10 \                     # numero di task paralleli
    --max-retries=3 \                # retry per task fallito
    --task-timeout=3600 \            # timeout per task (1 ora)
    --cpu=2 \
    --memory=2Gi \
    --set-env-vars="BATCH_ID=run-001"

# Eseguire il job
gcloud run jobs execute my-batch-job --region=europe-west8

# Esecuzione con override variabili
gcloud run jobs execute my-batch-job \
    --region=europe-west8 \
    --update-env-vars="BATCH_ID=run-002"

# Verificare lo stato dell'esecuzione
gcloud run jobs executions list --job=my-batch-job --region=europe-west8
gcloud run jobs executions describe EXECUTION_ID --region=europe-west8

# Schedulare tramite Cloud Scheduler
gcloud scheduler jobs create http my-batch-schedule \
    --schedule="0 2 * * *" \
    --uri="https://europe-west8-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/my-project/jobs/my-batch-job:run" \
    --message-body='{}' \
    --oauth-service-account-email=scheduler-sa@my-project.iam.gserviceaccount.com \
    --location=europe-west8
```

---

## Networking

### Ingress: Controllo Accesso in Entrata

Cloud Run offre tre modalità di ingress che determinano da dove può arrivare traffico:

| Modalità | Descrizione | Use case |
|---|---|---|
| `all` | Pubblico su internet (default) | API pubbliche, frontend |
| `internal` | Solo risorse interne GCP (VPC, Cloud Run, GKE) | Servizi interni, microservizi privati |
| `internal-and-cloud-load-balancing` | Internal + richieste tramite GCLB | Con HTTPS Load Balancer e Cloud Armor |

```bash
# Rendere il servizio interno (non raggiungibile da internet)
gcloud run services update my-service \
    --ingress=internal \
    --region=europe-west8

# Con Load Balancer (per Cloud Armor, WAF, custom domain)
gcloud run services update my-service \
    --ingress=internal-and-cloud-load-balancing \
    --region=europe-west8
```

### Egress: Connessione a Risorse Private

Per accedere a risorse in VPC (Cloud SQL via IP privato, Redis, VM interne), Cloud Run supporta due metodi:

**1. Direct VPC Egress** (consigliato — gen2):

```bash
# Connettere Cloud Run al VPC tramite Direct VPC Egress
gcloud run services update my-service \
    --region=europe-west8 \
    --network=production-vpc \
    --subnet=europe-west8-subnet \
    --vpc-egress=all-traffic         # o private-ranges-only
```

**2. Serverless VPC Access Connector** (legacy):

```bash
# Creare il connector
gcloud compute networks vpc-access connectors create my-connector \
    --region=europe-west8 \
    --subnet=vpc-connector-subnet \
    --min-instances=2 \
    --max-instances=10

# Usare il connector da Cloud Run
gcloud run services update my-service \
    --region=europe-west8 \
    --vpc-connector=my-connector \
    --vpc-egress=all-traffic
```

!!! tip "Direct VPC Egress vs Connector"
    **Direct VPC Egress** è il metodo moderno (sandbox gen2): nessun componente aggiuntivo da gestire, latenza inferiore, costo minore. Usa VPC Connector solo per servizi già esistenti che lo usano o per compatibilità con regioni che non supportano Direct VPC Egress.

### Connessione a Cloud SQL

```bash
# Metodo 1: Cloud SQL Proxy (via socket Unix — raccomandato)
# Il proxy viene iniettato come container sidecar automaticamente
gcloud run services update my-service \
    --add-cloudsql-instances=my-project:europe-west8:my-db \
    --set-env-vars="DB_SOCKET_PATH=/cloudsql/my-project:europe-west8:my-db"

# Metodo 2: IP privato via Direct VPC Egress
# Configurare il VPC, poi connettersi all'IP privato direttamente
```

---

## Autenticazione e IAM

### Autenticazione Servizio-a-Servizio

Cloud Run usa IAM per proteggere i servizi: solo le identità con il ruolo `roles/run.invoker` possono invocare un servizio non pubblico.

```bash
# Permettere a un service account di invocare il servizio
gcloud run services add-iam-policy-binding my-service \
    --region=europe-west8 \
    --member="serviceAccount:caller-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Rendere il servizio pubblico (senza autenticazione)
gcloud run services add-iam-policy-binding my-service \
    --region=europe-west8 \
    --member="allUsers" \
    --role="roles/run.invoker"

# Verificare le policy IAM del servizio
gcloud run services get-iam-policy my-service --region=europe-west8
```

### Chiamata Autenticata da Codice

Per chiamare un servizio Cloud Run autenticato, il caller deve aggiungere un **OIDC token** nell'header `Authorization`:

```bash
# Ottenere un token OIDC per chiamare il servizio (da CLI)
TOKEN=$(gcloud auth print-identity-token \
    --audiences=https://my-service-xxxx-xx.a.run.app)
curl -H "Authorization: Bearer $TOKEN" \
    https://my-service-xxxx-xx.a.run.app/api/v1/data
```

```python
# Python — chiamata autenticata service-to-service
import google.auth.transport.requests
import google.oauth2.id_token

def call_cloud_run_service(url: str) -> dict:
    """Chiama un servizio Cloud Run privato con OIDC token."""
    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, url)

    import requests
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {id_token}"}
    )
    response.raise_for_status()
    return response.json()
```

### Identity del Servizio

```bash
# Assegnare un service account dedicato al servizio (best practice)
gcloud run services update my-service \
    --region=europe-west8 \
    --service-account=my-app-sa@my-project.iam.gserviceaccount.com

# Il SA del servizio deve avere solo i permessi minimi necessari
# Esempio: leggere da Cloud Storage
gcloud projects add-iam-policy-binding my-project \
    --member="serviceAccount:my-app-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

!!! warning "Non usare il service account di default di Compute Engine"
    Il SA di default `PROJECT_NUMBER-compute@developer.gserviceaccount.com` ha il ruolo `Editor` sull'intero progetto. Creare sempre un SA dedicato con i permessi minimi (principio del least privilege).

---

## Best Practices

!!! tip "Impostare min-instances=1 per servizi critici"
    Con `min-instances=0` (default), ogni periodo di inattività produce un **cold start** alla richiesta successiva. Per servizi con SLA di latenza, impostare `--min-instances=1`: un'istanza sempre calda elimina il cold start al costo di ~1 vCPU/ora anche in idle.

!!! warning "Timeout richieste e cold start"
    Il timeout di Cloud Run include il cold start. Se un container impiega 3 secondi ad avviarsi e il timeout è 5 secondi, alcune richieste scadranno durante i cold start. Dimensionare il timeout tenendo conto del tempo di avvio: `timeout > startup_time + max_request_time`.

```bash
# Struttura Dockerfile ottimizzata per cold start rapidi
# 1. Usare immagini base leggere (alpine, distroless)
# 2. Multi-stage build per minimizzare la dimensione
# 3. Copiare le dipendenze PRIMA del codice sorgente (cache Docker)
```

```dockerfile
# Esempio: Go service con immagine distroless (cold start < 100ms)
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/server ./cmd/server

FROM gcr.io/distroless/static-debian12
COPY --from=builder /bin/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

**Checklist best practices Cloud Run:**

- [ ] Immagine base leggera (distroless, alpine) per cold start rapidi
- [ ] Service account dedicato con permessi minimi — mai Compute Engine default SA
- [ ] `min-instances=1` per servizi con SLA di latenza
- [ ] Secrets tramite Secret Manager, non variabili d'ambiente hardcoded
- [ ] Health check (`startupProbe` + `livenessProbe`) per rilevare crash
- [ ] `ingress=internal` per servizi non esposti a internet
- [ ] CPU always-on solo se necessario (background tasks) — aumenta i costi
- [ ] Sandbox gen2 (`--execution-environment=gen2`) per performance migliori e Direct VPC Egress
- [ ] Tag le revision per test diretto prima di promuovere traffico (`--no-traffic --tag=canary`)
- [ ] Configurare Cloud Logging e Cloud Monitoring alert su error rate e latenza p99

---

## Troubleshooting

**Problema: Cold start troppo lento — richieste scadono alla prima chiamata dopo inattività**

```bash
# Sintomo: prime richieste dopo idle > 30s hanno latenza molto alta o 504
# Diagnosi: verificare il tempo di avvio del container
gcloud run services describe my-service \
    --region=europe-west8 \
    --format="value(spec.template.metadata.annotations)"
# Cercare: autoscaling.knative.dev/minScale

# Soluzione 1: impostare min-instances per evitare scale-to-zero
gcloud run services update my-service \
    --region=europe-west8 \
    --min-instances=1

# Soluzione 2: aumentare il timeout per dare tempo al cold start
gcloud run services update my-service \
    --region=europe-west8 \
    --timeout=60

# Soluzione 3: ottimizzare il container (vedere Dockerfile sopra)
# Verificare il startup time reale dai log
gcloud logging read \
    'resource.type="cloud_run_revision" AND textPayload:"started"' \
    --project=my-project \
    --limit=10
```

**Problema: Servizio scala a zero ma non vuoi che lo faccia — costi zero ma cold start inaccettabili**

```bash
# Fissare un minimo di istanze sempre attive
gcloud run services update my-service \
    --region=europe-west8 \
    --min-instances=2    # 2 istanze sempre calde per HA

# NOTA: min-instances > 0 genera costi anche senza traffico
# Verificare il costo stimato prima di abilitare
gcloud run services describe my-service \
    --region=europe-west8 \
    --format="value(spec.template.spec.containers[0].resources)"
```

**Problema: `Error: Container failed to start` — il servizio non risponde sulla porta**

```bash
# Sintomo: il deploy avviene ma le richieste ricevono 503
# Causa più comune: il container non ascolta sulla porta giusta

# Diagnosi: verificare i log del container al cold start
gcloud logging read \
    'resource.type="cloud_run_revision" AND severity>=ERROR' \
    --project=my-project \
    --limit=20 \
    --format="table(timestamp,textPayload)"

# Verifica che il container usi la variabile PORT
# Cloud Run inietta PORT=8080 — il server DEVE ascoltare su quella porta
# Esempio Go:
#   port := os.Getenv("PORT")
#   if port == "" { port = "8080" }
#   http.ListenAndServe(":"+port, nil)

# Test locale simulando Cloud Run
docker run -p 8080:8080 -e PORT=8080 \
    europe-west8-docker.pkg.dev/my-project/my-repo/my-app:latest
curl http://localhost:8080/healthz
```

**Problema: `403 Forbidden` sulle chiamate service-to-service**

```bash
# Sintomo: servizio A chiama servizio B e riceve 403
# Causa: il SA di servizio A non ha il ruolo run.invoker su servizio B

# Diagnosi: verificare il SA del servizio chiamante
gcloud run services describe service-a \
    --region=europe-west8 \
    --format="value(spec.template.spec.serviceAccountName)"

# Verificare le policy IAM del servizio destinatario
gcloud run services get-iam-policy service-b --region=europe-west8

# Soluzione: aggiungere il binding IAM mancante
gcloud run services add-iam-policy-binding service-b \
    --region=europe-west8 \
    --member="serviceAccount:service-a-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Verificare che il codice aggiunga il token OIDC nell'Authorization header
# (non basta il token di accesso — serve specificare l'audience corretto)
```

**Problema: Cloud Run non riesce a raggiungere Cloud SQL o risorse VPC private**

```bash
# Sintomo: connection timeout verso IP privati, Cloud SQL via private IP
# Causa: VPC egress non configurato

# Diagnosi: verificare la configurazione di rete del servizio
gcloud run services describe my-service \
    --region=europe-west8 \
    --format="value(spec.template.metadata.annotations)" | \
    grep -E "vpc|network"

# Soluzione: abilitare Direct VPC Egress (sandbox gen2 richiesto)
gcloud run services update my-service \
    --region=europe-west8 \
    --execution-environment=gen2 \
    --network=production-vpc \
    --subnet=europe-west8-subnet \
    --vpc-egress=private-ranges-only   # solo IP privati via VPC

# Verificare connettività dopo la modifica
gcloud run services describe my-service \
    --region=europe-west8 \
    --format="value(spec.template.metadata.annotations['run.googleapis.com/network-interfaces'])"
```

**Problema: Autoscaling non avviene abbastanza velocemente — richieste in timeout durante spike**

```bash
# Sintomo: durante picchi di traffico improvvisi, molte richieste ricevono 429 o 503
# Causa: il scaling reagisce ma le nuove istanze impiegano secondi ad avviarsi

# Soluzione 1: aumentare la concorrenza per servire più richieste per istanza
gcloud run services update my-service \
    --region=europe-west8 \
    --concurrency=200  # aumentare se l'app è thread-safe

# Soluzione 2: usare startup CPU boost (gen2) per ridurre i cold start
# In YAML:
#   run.googleapis.com/startup-cpu-boost: "true"

# Soluzione 3: pre-warm con min-instances
gcloud run services update my-service \
    --min-instances=5 \   # 5 istanze pronte ad assorbire il traffico iniziale
    --max-instances=200
```

---

## Relazioni

??? info "GKE — Kubernetes Managed su GCP"
    GKE è l'alternativa a Cloud Run per workload che richiedono orchestrazione avanzata: DaemonSet, StatefulSet con storage persistente, sidecar, Service Mesh. Per applicazioni stateless HTTP, Cloud Run è più semplice e più economico. Per applicazioni complesse o con stato, GKE offre il controllo necessario.

    **Approfondimento →** [Google Kubernetes Engine (GKE)](../containers/gke.md)

??? info "GCP — Panoramica Servizi"
    Cloud Run si posiziona nella categoria compute serverless di GCP, insieme ad App Engine (PaaS tradizionale) e Cloud Functions (FaaS event-driven). La panoramica GCP include la tabella comparativa tra tutti i servizi compute di Google Cloud.

    **Approfondimento →** [Panoramica GCP](../fondamentali/panoramica.md)

---

## Riferimenti

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Services YAML Reference](https://cloud.google.com/run/docs/reference/rest/v1/namespaces.services)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Autoscaling Cloud Run](https://cloud.google.com/run/docs/about-instance-autoscaling)
- [Direct VPC Egress](https://cloud.google.com/run/docs/configuring/vpc-direct-vpc)
- [Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [Authentication and Cloud Run](https://cloud.google.com/run/docs/authenticating/overview)
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/tips/general)
- [Container Contract (PORT, health checks)](https://cloud.google.com/run/docs/container-contract)
- [Traffic Splitting](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)
