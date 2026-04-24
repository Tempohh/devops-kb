# KB Saturation Report — 2026-04-04

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| messaging/kafka | ~35 | 90% | Expert | Saturata: fondamentali, pattern, sicurezza, ops, dev tutti coperti |
| containers/kubernetes | ~13 | 85% | Advanced | Molto completa; gateway-api appena aggiunto (prop-023) |
| cloud/aws | ~31 | 80% | Advanced | Ben sviluppata; qualche gap su Fargate e ECS standalone |
| cloud/azure | ~27 | 75% | Advanced | Buona copertura; manca Azure Container Apps |
| networking | ~31 | 75% | Advanced | Ottima; protocolli, service mesh, kubernetes, load-balancing |
| databases | ~21 | 70% | Intermediate | Buona; manca TimescaleDB e database grafici |
| containers/docker | ~6 | 70% | Advanced | Completo per uso operativo |
| messaging/rabbitmq | ~6 | 65% | Intermediate | Buona copertura base, manca Streams (RabbitMQ 3.9+) |
| security | ~17 | 65% | Advanced | Buona; manca SIEM integration e zero-trust enforcement tools |
| ci-cd | ~20 | 60% | Intermediate | Buona ma manca performance testing e quality gates (SonarQube) |
| ai | ~19 | 60% | Intermediate | Discreta; manca LangChain/LangGraph e observability per LLM |
| monitoring | ~14 | 55% | Intermediate | Gap critico: scalabilità Prometheus non coperta |
| dev | ~18 | 55% | Intermediate | Discreto; manca GraphQL, API versioning, gRPC da codice |
| cloud/gcp | ~11 | 40% | Beginner | Sottosviluppata vs AWS/Azure; mancano storage, SQL, networking avanzato |
| iac | ~9 | 40% | Intermediate | Gap: OpenTofu assente, no Crossplane, no CDK Terraform |
| containers/kustomize | ~1 | 25% | Advanced only | Critico: esiste solo avanzato.md, manca entry-point fondamentali |
| cloud/finops | ~2 | 20% | Beginner | Molto sottosviluppata: mancano multi-cloud tagging, Kubecost avanzato |

## Categorie vicine alla saturazione

- **messaging/kafka**: 35 file coprono ogni aspetto del sistema. Ulteriori aggiunte
  rischiano di essere ridondanti o micro-specializzazioni. Prossima aggiunta utile:
  solo se emerge un nuovo pattern (Kafka + AI pipelines).

- **containers/kubernetes**: 13 file coprono fondamentali, networking, sicurezza,
  storage, autoscaling, multi-cluster. Gateway API appena aggiunto (prop-023).
  Ulteriori gap marginali (es. Virtual Cluster con vCluster).

- **cloud/aws**: 31 file molto completi. Eventuali gap: Fargate standalone,
  AWS Lambda Powertools, Bedrock (AI).

## Categorie con gap reali

- **containers/kustomize**: solo `avanzato.md` — manca l'entry-point fondamentali.
  Un DevOps che inizia non ha dove atterrare. Gap critico di connettività narrativa.
  → prop-024 (high)

- **iac**: OpenTofu completamente assente nonostante il cambio licenza Terraform
  BSL sia l'evento IaC più discusso degli ultimi 2 anni. Manca anche Crossplane
  (Kubernetes-native IaC, CNCF Graduated) e pattern avanzati Terragrunt.
  → prop-025 (high), + futura prop per Crossplane

- **monitoring**: prometheus.md copre la configurazione base ma non la scalabilità.
  Thanos e VictoriaMetrics sono assenti — gap operativo reale per cluster multipli.
  → prop-026 (high)

- **cloud/gcp**: 11 file contro 31 di AWS. Cloud Storage mancante (usato da quasi
  ogni workload GCP), Cloud SQL assente, networking avanzato non coperto.
  → prop-027 (medium)

- **ci-cd/testing**: test-strategy.md raccomanda performance test ma la KB non
  ha nessuna guida su k6/Gatling/JMeter. Gap tra raccomandazione e strumenti.
  → prop-028 (medium)

## Gap identificati ma non proposti (priorità bassa o troppo niche)

- **TimescaleDB**: nessun file su time-series databases utile per IoT e metrics storage
- **GraphQL**: dev/api ha solo rest-openapi.md, manca GraphQL e federation
- **Azure Container Apps**: compute Azure non copre ACA (serverless con autoscaling a zero)
- **RabbitMQ Streams**: nuova feature 3.9+ per alta-throughput streaming
- **Crossplane**: Kubernetes-native IaC (CNCF Graduated) — omesso da iac e containers

## Prossima sessione consigliata

**Data**: dopo approvazione ed esecuzione di prop-024/025/026

**Focus tematico**: IaC completamento (Crossplane, Terragrunt) oppure GCP deep-dive.

**Priorità suggerita per approvazione**:
1. prop-024 (Kustomize fondamentali) — risolve gap narrativo immediato, effort small
2. prop-025 (OpenTofu) — topico urgente, effort small
3. prop-026 (Thanos/VictoriaMetrics) — gap operativo reale, effort medium
4. prop-027 (GCP Cloud Storage) — completamento GCP, effort small
5. prop-028 (Performance testing) — completa piramide testing, effort medium
|-----------|-------|------------|-------|------|
| messaging/kafka | ~22 | 90% | deep | Saturata — fondamenti, sicurezza, streams, connect, K8s, schema registry |
| cloud/azure | ~30 | 80% | deep | Completa: compute/networking/db/monitoring/identity/messaging/security |
| cloud/aws | ~15 | 72% | good | Storage/database/monitoring/security coperti; compute leggero |
| containers/kubernetes | ~14 | 78% | advanced | Architettura, workloads, networking, sicurezza, storage, scheduling avanzato |
| security | ~18 | 72% | advanced | Supply chain, authn/authz, PKI, runtime (parziale), compliance |
| databases | ~22 | 75% | advanced | PostgreSQL, NoSQL (Redis/Mongo/Cassandra/ES), fondamentali, replica HA |
| networking | ~30 | 70% | advanced | Fondamentali, service-mesh, load-balancing, K8s networking, API gateway, sicurezza |
| monitoring | ~15 | 72% | advanced | Prometheus rules, Grafana, Loki, Jaeger/Tempo, OTel Collector, SRE |
| ci-cd | ~22 | 70% | advanced | Jenkins/GHA/GitLab/GitOps/strategie/testing/platform engineering |
| containers/docker | ~6 | 70% | good | Core ben coperto |
| messaging/rabbitmq | ~6 | 62% | good | Architettura, affidabilità, clustering, deployment, features-avanzate, vs-kafka |
| ai | ~20 | 65% | advanced | fondamentali, modelli, agents, sviluppo, training, MLOps — copertura buona |
| dev | ~22 | 58% | intermediate | Linguaggi, resilienza, sicurezza applicativa — api/ e testing/ vuote |
| cloud/gcp | ~12 | 48% | intermediate | Fondamentali/IAM/VPC/GKE/BigQuery/PubSub/monitoring — in crescita |
| containers/openshift | ~5 | 55% | intermediate | Architettura, build, gitops, operators, sicurezza |
| iac/terraform | ~4 | 55% | intermediate | Fondamentali/state/moduli/testing — manca workflow CI/CD |
| iac/ansible | ~2 | 30% | thin | Fondamentali + roles — manca dynamic inventory, CI/CD integration |
| iac/pulumi | ~2 | 40% | thin | Fondamentali + stacks — manca testing, provider patterns avanzati |
| cloud/finops | ~1 | 20% | thin | Solo fondamentali — manca tooling pratico (Kubecost/OpenCost) |
| dev/api | ~0 | 5% | none | Solo _index — zero contenuto (REST design, OpenAPI) |
| dev/testing | ~0 | 5% | none | Solo _index — zero contenuto (TDD, test doubles) |

## Categorie vicine alla saturazione

- **messaging/kafka**: ~22 file con copertura quasi completa. Ulteriori aggiunte hanno rendimento marginale decrescente. Gap residuo: MirrorMaker 2 per replica multi-cluster.
- **cloud/azure**: ~30 file, copertura estesa. Gap residuo: Azure Container Apps, Policy Initiative avanzate.
- **containers/kubernetes**: ~14 file. Gap residuo: Gateway API (già in prop-023), Kubernetes 1.30+ features.
- **monitoring**: ~15 file. Gap residuo: Thanos/Cortex per Prometheus scalabile in produzione.

## Categorie con gap reali

### Priorità HIGH (bloccanti per operatività)

1. **dev/api/** (0 contenuto): Categoria completamente vuota. REST API design e OpenAPI sono le skill più trasversali per backend developer e DevOps. → **prop-019** (HIGH)

2. **security/runtime/** (1 file): Solo seccomp-apparmor.md. Falco è il tool standard CNCF per runtime threat detection — obbligatorio per compliance SOC2/ISO27001. → **prop-020** (HIGH)

3. **iac/terraform/** (4 file, manca CI/CD): Fondamentali/state/moduli/testing presenti ma il workflow collaborativo (Atlantis, PR-based plan/apply) è assente. Gap critico per team. → **prop-021** (HIGH)

### Priorità MEDIUM

4. **cloud/finops/** (1 file): fondamentali.md presente ma nessun tool concreto. Kubecost/OpenCost per Kubernetes cost allocation è la richiesta più comune dai team platform. → **prop-022** (MEDIUM)

5. **networking/kubernetes/** (manca Gateway API): ingress.md presente ma il successore ufficiale (GA in K8s 1.28+) non è documentato. Rilevanza crescente. → **prop-023** (MEDIUM)

### Non proposte in questa sessione (prossimo ciclo)

- **dev/testing/**: Categoria vuota (TDD, test doubles, property-based testing) — priorità dopo prop-019
- **iac/ansible/** e **iac/pulumi/**: Dynamic inventory, Molecule, provider patterns avanzati — attendere prop-021 (terraform CI/CD) come riferimento
- **cloud/gcp/**: Cloud SQL, Cloud Build, Artifact Registry — copertura in crescita, prossimo ciclo

## Prossima sessione consigliata

**Data suggerita**: dopo approvazione ed esecuzione di prop-019 → prop-023

**Focus tematico**:
1. `dev/testing/` — TDD e pattern di unit testing (categoria ancora vuota)
2. `iac/ansible/` — dynamic inventory e pipeline CI/CD Ansible
3. `cloud/gcp/` — completamento (Cloud SQL, Cloud Build/Artifact Registry)
4. `cloud/finops/` — Infracost per Terraform (complementare a Kubecost)

**Indicatore di rientro**: quando dev/api/ avrà ≥2 file e iac/terraform/ includerà il workflow CI/CD (prop-021 eseguita).
