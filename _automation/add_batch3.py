"""Aggiunge il batch 3 di task alla coda state.yaml — gap reali identificati da inventory completo."""
import yaml
from pathlib import Path

state_file = Path(__file__).parent / "state.yaml"
with open(state_file, encoding="utf-8") as f:
    state = yaml.safe_load(f)

new_tasks = [
    # ── GCP — completamente assente ──────────────────────────────────────────
    {
        "id": "201", "type": "new_topic",
        "path": "docs/cloud/gcp/fondamentali/panoramica.md",
        "category": "cloud/gcp", "priority": "P1",
        "reason": "GCP e' il terzo cloud provider ma manca completamente dalla KB. Solo AWS e Azure sono coperti. Fondamentali GCP: progetti, IAM, billing, regioni/zone, Google Cloud SDK.",
        "worth_if": "Team che usano o valutano GCP — base imprescindibile",
        "skip_if": "Gia' presente in altro file GCP",
        "status": "pending"
    },
    {
        "id": "202", "type": "new_topic",
        "path": "docs/cloud/gcp/containers/gke.md",
        "category": "cloud/gcp", "priority": "P1",
        "reason": "GKE e' il Kubernetes managed di Google — il piu' maturo tra i cloud provider. Autopilot vs Standard, Workload Identity, node pools, release channels, upgrade automatici.",
        "worth_if": "Team con carichi containerizzati su GCP",
        "skip_if": "Gia' trattato in file GCP esistenti",
        "status": "pending"
    },
    # ── Incident Management — gap SRE pratico ───────────────────────────────
    {
        "id": "203", "type": "new_topic",
        "path": "docs/monitoring/sre/incident-management.md",
        "category": "monitoring", "priority": "P1",
        "reason": "Gestione degli incidenti e' il pilastro pratico dell'SRE. Severity levels, on-call rotation (PagerDuty/OpsGenie), runbook structure, war room, blameless postmortem, MTTR improvement. Completa il terzetto SLO/error-budget.",
        "worth_if": "Team con on-call e produzione critica",
        "skip_if": "Gia' coperto in slo-sla-sli.md o error-budget.md",
        "status": "pending"
    },
    # ── Chaos Engineering — testing affidabilita' ───────────────────────────
    {
        "id": "204", "type": "new_topic",
        "path": "docs/monitoring/sre/chaos-engineering.md",
        "category": "monitoring", "priority": "P2",
        "reason": "Chaos Engineering: Chaos Monkey, Litmus Chaos per Kubernetes, scenari (pod failure, network latency, CPU stress, node drain), GameDay, steady state hypothesis. Completa il set SRE.",
        "worth_if": "Team con alta disponibilita' e volonta' di testare i failure modes",
        "skip_if": "Gia' coperto in file SRE o monitoring esistenti",
        "status": "pending"
    },
    # ── FinOps — ottimizzazione costi cloud ──────────────────────────────────
    {
        "id": "205", "type": "new_topic",
        "path": "docs/cloud/finops/fondamentali.md",
        "category": "cloud", "priority": "P2",
        "reason": "FinOps e' la disciplina di ottimizzazione costi cloud. Reserved Instances vs Spot, rightsizing, tagging strategy, cost allocation, unit economics, AWS Cost Explorer / GCP Billing / Azure Cost Management.",
        "worth_if": "Team con cloud spend rilevante e interesse a ottimizzare",
        "skip_if": "Gia' trattato nei file billing/pricing di AWS o Azure",
        "status": "pending"
    },
    # ── Platform Engineering / IDP ───────────────────────────────────────────
    {
        "id": "206", "type": "new_topic",
        "path": "docs/ci-cd/platform-engineering/backstage.md",
        "category": "ci-cd", "priority": "P2",
        "reason": "Backstage (CNCF) e' lo strumento di riferimento per Internal Developer Platforms. Software catalog, TechDocs, scaffolder templates, plugins. Trend in forte crescita nei team DevOps maturi.",
        "worth_if": "Team con 10+ microservizi che vogliono migliorare la developer experience",
        "skip_if": "Gia' presente in file CI/CD esistenti",
        "status": "pending"
    },
    # ── eBPF — networking e security avanzati ────────────────────────────────
    {
        "id": "207", "type": "new_topic",
        "path": "docs/networking/fondamentali/ebpf.md",
        "category": "networking", "priority": "P2",
        "reason": "eBPF e' la tecnologia abilitante di Cilium, Falco, Pixie, Tetragon. Permette networking e security a livello kernel senza patching. Fondamentale per comprendere CNI moderni e runtime security.",
        "worth_if": "Team che usano Cilium, Falco o vogliono capire le basi tecnologiche dei CNI moderni",
        "skip_if": "Gia' trattato in cni.md o networking/kubernetes/",
        "status": "pending"
    },
    # ── GCP compute e storage ────────────────────────────────────────────────
    {
        "id": "208", "type": "new_topic",
        "path": "docs/cloud/gcp/compute/cloud-run.md",
        "category": "cloud/gcp", "priority": "P2",
        "reason": "Cloud Run e' il serverless container di GCP — fully managed, scale-to-zero, revision traffic splitting. Piu' flessibile di Lambda per container esistenti. Complementare a GKE per workload stateless.",
        "worth_if": "Team che vogliono serverless con container su GCP",
        "skip_if": "Gia' trattato in file GCP esistenti",
        "status": "pending"
    },
    # ── Terraform avanzato ───────────────────────────────────────────────────
    {
        "id": "209", "type": "new_topic",
        "path": "docs/iac/terraform/testing.md",
        "category": "iac", "priority": "P2",
        "reason": "Testing del codice IaC: Terratest (Go), terraform validate/plan, conftest/OPA per policy, checkov per security scanning, tflint, pre-commit hooks. Gap: fondamentali/moduli/state esistono ma non il testing.",
        "worth_if": "Team che vogliono IaC con quality gate nel CI/CD",
        "skip_if": "Gia' trattato in fondamentali.md o moduli.md",
        "status": "pending"
    },
    # ── Kubernetes avanzato ──────────────────────────────────────────────────
    {
        "id": "210", "type": "new_topic",
        "path": "docs/containers/kubernetes/multi-cluster.md",
        "category": "containers", "priority": "P2",
        "reason": "Gestione multi-cluster K8s: Cluster API, Rancher, Fleet (Rancher), Argo CD multi-cluster, Crossplane, KubeFed v2. Fondamentale per infrastrutture enterprise con piu' cluster (dev/staging/prod, geo-distribuzione).",
        "worth_if": "Team con 3+ cluster Kubernetes da gestire",
        "skip_if": "Gia' trattato in architettura.md o altri file K8s",
        "status": "pending"
    },
    # ── GCP networking e managed services ───────────────────────────────────
    {
        "id": "211", "type": "new_topic",
        "path": "docs/cloud/gcp/dati/bigquery.md",
        "category": "cloud/gcp", "priority": "P3",
        "reason": "BigQuery e' il data warehouse serverless di GCP — leader nel cloud analytics. Slot-based pricing, partitioned/clustered tables, federated queries, BQML, streaming inserts. Manca completamente.",
        "worth_if": "Team con analytics o data engineering su GCP",
        "skip_if": "Gia' presente in file GCP esistenti",
        "status": "pending"
    },
    {
        "id": "212", "type": "new_topic",
        "path": "docs/monitoring/sre/capacity-planning.md",
        "category": "monitoring", "priority": "P3",
        "reason": "Capacity planning: demand forecasting, load testing (k6, Locust, JMeter), headroom management, cost vs performance tradeoff. Completa il set SRE con un focus proattivo.",
        "worth_if": "Team che gestiscono crescita del traffico e devono evitare over/under provisioning",
        "skip_if": "Gia' trattato in SLO o error-budget in modo sufficiente",
        "status": "pending"
    },
]

# Verifica: non aggiungere task con path gia' in coda o completati
existing_paths = {item.get("path", "") for item in state.get("queue", [])}
existing_paths.update(c.get("path", "") for c in state.get("completed", []))
to_add = [t for t in new_tasks if t["path"] not in existing_paths]

state["queue"].extend(to_add)

with open(state_file, "w", encoding="utf-8") as f:
    f.write("# Stato del sistema di automazione KB\n")
    f.write("# Aggiornato automaticamente - non modificare 'completed' manualmente\n\n")
    yaml.dump(state, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

print(f"Aggiunti {len(to_add)} nuovi task (batch 3). Saltati {len(new_tasks)-len(to_add)} duplicati.")
for t in to_add:
    print(f"  [{t['priority']}] {t['id']}: {t['path']}")
