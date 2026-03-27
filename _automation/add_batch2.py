"""Aggiunge il batch 2 di task alla coda state.yaml."""
import yaml
from pathlib import Path

state_file = Path(__file__).parent / "state.yaml"
with open(state_file, encoding="utf-8") as f:
    state = yaml.safe_load(f)

new_tasks = [
    {
        "id": "101", "type": "new_topic",
        "path": "docs/containers/kubernetes/networking.md",
        "category": "containers", "priority": "P1",
        "reason": "Networking Kubernetes: CNI, Services (ClusterIP/NodePort/LoadBalancer), Ingress, NetworkPolicy, DNS interno. Gap critico: workloads.md esiste ma il networking e' assente.",
        "worth_if": "Qualsiasi team che gestisce K8s in produzione",
        "skip_if": "Gia' coperto in dettaglio da un file esistente",
        "status": "pending"
    },
    {
        "id": "102", "type": "new_topic",
        "path": "docs/ci-cd/tools/github-actions.md",
        "category": "ci-cd", "priority": "P1",
        "reason": "GitHub Actions e' il CI/CD piu' usato. Manca completamente dalla KB. Workflow YAML, jobs/steps, matrix, secrets, environments, reusable workflows, caching.",
        "worth_if": "Qualsiasi team che usa GitHub per il codice sorgente",
        "skip_if": "Gia' presente in altro file CI/CD",
        "status": "pending"
    },
    {
        "id": "103", "type": "new_topic",
        "path": "docs/ci-cd/tools/argocd.md",
        "category": "ci-cd", "priority": "P1",
        "reason": "ArgoCD e' lo standard per GitOps su Kubernetes. App, ApplicationSet, sync policies, RBAC, multi-cluster. Complementare a Helm e Kustomize.",
        "worth_if": "Team con K8s che vogliono GitOps e deployment dichiarativo",
        "skip_if": "Gia' trattato in altri file GitOps/CI-CD",
        "status": "pending"
    },
    {
        "id": "104", "type": "new_topic",
        "path": "docs/security/iam/oauth2-oidc.md",
        "category": "security", "priority": "P1",
        "reason": "OAuth2 e OIDC sono i protocolli di autenticazione/autorizzazione moderni. Authorization Code Flow, PKCE, JWT, Keycloak, scope, token refresh. Fondamentale per qualsiasi applicazione moderna.",
        "worth_if": "Team che sviluppano o gestiscono applicazioni con autenticazione",
        "skip_if": "Gia' coperto adeguatamente in security/",
        "status": "pending"
    },
    {
        "id": "105", "type": "new_topic",
        "path": "docs/containers/kubernetes/ingress.md",
        "category": "containers", "priority": "P2",
        "reason": "Ingress controller e' il punto di ingresso HTTP/HTTPS in K8s. nginx-ingress, Traefik, TLS termination, path routing, rate limiting, canary. Gap evidente con workloads/networking.",
        "worth_if": "Qualsiasi team con applicazioni HTTP esposte su K8s",
        "skip_if": "Gia' coperto in networking.md",
        "status": "pending"
    },
    {
        "id": "106", "type": "new_topic",
        "path": "docs/cloud/aws/containers/eks.md",
        "category": "cloud/aws", "priority": "P2",
        "reason": "EKS e' il Kubernetes managed su AWS: il deployment K8s piu' comune in enterprise. Node groups, Fargate, IRSA, add-on management, upgrade strategy.",
        "worth_if": "Team che usano AWS con carichi containerizzati",
        "skip_if": "Gia' trattato in file AWS esistenti",
        "status": "pending"
    },
    {
        "id": "107", "type": "new_topic",
        "path": "docs/databases/sql/postgresql-produzione.md",
        "category": "databases", "priority": "P2",
        "reason": "PostgreSQL in produzione: replication (streaming, logical), PgBouncer, VACUUM/autovacuum tuning, slow query analysis, backup con WAL-G, extensions pg_stat_statements.",
        "worth_if": "Team con PostgreSQL in produzione",
        "skip_if": "Gia' coperto in databases/sql/",
        "status": "pending"
    },
    {
        "id": "108", "type": "new_topic",
        "path": "docs/networking/protocolli/http2-http3.md",
        "category": "networking", "priority": "P2",
        "reason": "HTTP/2 (multiplexing, server push, header compression) e HTTP/3 (QUIC, 0-RTT) sono fondamentali per capire performance web e configurare load balancer/reverse proxy moderni.",
        "worth_if": "Chi configura nginx, load balancer, CDN o ottimizza API",
        "skip_if": "Gia' trattato in tcp-ip.md o file networking esistenti",
        "status": "pending"
    },
    {
        "id": "109", "type": "new_topic",
        "path": "docs/containers/kubernetes/helm.md",
        "category": "containers", "priority": "P2",
        "reason": "Helm e' il package manager de-facto per K8s. Charts, templates, values, hooks, OCI registries, Helmfile. Praticamente ogni K8s deployment usa Helm.",
        "worth_if": "Tutti i team che gestiscono applicazioni su Kubernetes",
        "skip_if": "Gia' trattato in file K8s esistenti",
        "status": "pending"
    },
    {
        "id": "110", "type": "new_topic",
        "path": "docs/security/network/zero-trust.md",
        "category": "security", "priority": "P2",
        "reason": "Zero Trust Architecture: never trust always verify, micro-segmentation, service mesh mTLS, BeyondCorp. Rilevante per K8s, cloud e compliance enterprise.",
        "worth_if": "Team con requisiti di sicurezza enterprise o compliance",
        "skip_if": "Gia' trattato in mutual-tls.md o altro file security",
        "status": "pending"
    },
    {
        "id": "111", "type": "new_topic",
        "path": "docs/cloud/aws/compute/lambda.md",
        "category": "cloud/aws", "priority": "P3",
        "reason": "AWS Lambda: cold start, execution model, layers, event sources (API GW, SQS, S3), concurrency, SnapStart, cost optimization.",
        "worth_if": "Team con architetture event-driven o serverless su AWS",
        "skip_if": "Gia' trattato in file AWS esistenti",
        "status": "pending"
    },
    {
        "id": "112", "type": "new_topic",
        "path": "docs/ci-cd/tools/tekton.md",
        "category": "ci-cd", "priority": "P3",
        "reason": "Tekton e' il CI/CD nativo Kubernetes: Pipeline, Task, PipelineRun, Triggers. Complementare ad ArgoCD nel pattern CI (Tekton) + CD (ArgoCD).",
        "worth_if": "Team che vogliono CI/CD cloud-native",
        "skip_if": "GitHub Actions o altro CI/CD gia' copre il gap adeguatamente",
        "status": "pending"
    },
]

# Verifica: non aggiungere task con path gia' in coda
existing_paths = {item.get("path", "") for item in state.get("queue", [])}
to_add = [t for t in new_tasks if t["path"] not in existing_paths]

state["queue"].extend(to_add)

with open(state_file, "w", encoding="utf-8") as f:
    f.write("# Stato del sistema di automazione KB\n")
    f.write("# Aggiornato automaticamente - non modificare 'completed' manualmente\n\n")
    yaml.dump(state, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

print(f"Aggiunti {len(to_add)} nuovi task (batch 2). Saltati {len(new_tasks)-len(to_add)} duplicati.")
