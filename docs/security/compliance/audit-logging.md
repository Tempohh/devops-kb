---
title: "Audit Logging e Runtime Security"
slug: audit-logging
category: security
tags: [audit, logging, falco, siem, kubernetes-audit, compliance, runtime-security]
search_keywords: [audit logging security, kubernetes audit log, falco runtime security, siem integration, structured audit log, audit trail microservizi, security event logging, compliance logging, falco rules, falco kubernetes, falco helm, ebpf falco, falco alerts, falco output, log forwarding, fluentbit security, opensearch siem, elastic siem, cloudwatch security, aws cloudtrail, gcp cloud audit logs, azure monitor security, audit log retention, gdpr audit, sox audit, pci dss logging, iso27001 audit, security incident response, forensics kubernetes, log integrity, tamper-proof logging, audit log signing, who did what when]
parent: security/compliance/_index
related: [security/supply-chain/admission-control, security/secret-management/vault, security/autorizzazione/opa]
official_docs: https://falco.org/docs/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Audit Logging e Runtime Security

## Panoramica

Un sistema di audit risponde alla domanda: **"cosa è successo?"** Questo è fondamentale sia per il debugging operativo che per la risposta agli incidenti di sicurezza — e spesso è un requisito di compliance (SOC 2, ISO 27001, PCI-DSS, GDPR).

Ci sono tre livelli distinti di audit in un'architettura a microservizi:

```
Livello 1 — Application Audit
  Chi ha fatto cosa nell'applicazione
  Es: "utente mario ha cancellato l'ordine #456 alle 14:32"

Livello 2 — Infrastructure Audit (Kubernetes)
  Chi ha modificato il cluster
  Es: "CI pipeline ha scalato il Deployment orders da 3 a 5 alle 14:30"
  Es: "kubectl exec eseguito nel pod prod-db-0 dall'utente mario@corp"

Livello 3 — Runtime Security (Falco)
  Comportamento anomalo a runtime
  Es: "processo /bin/sh avviato nel container orders — possibile reverse shell"
  Es: "apertura di /etc/shadow nel container nginx — tentativo di privilege escalation"
```

---

## Application Audit Log — Structured Logging

Ogni evento significativo dell'applicazione deve essere loggato in formato strutturato:

```python
import structlog
import uuid
from datetime import datetime, timezone

# Configurazione structlog per audit
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ]
)

audit_logger = structlog.get_logger("audit")

def log_audit_event(
    event: str,
    actor: dict,          # chi ha compiuto l'azione
    resource: dict,       # su cosa
    action: str,          # cosa
    outcome: str,         # success / failure / error
    context: dict = None  # contesto aggiuntivo
):
    audit_logger.info(
        event,
        # Identità dell'attore
        actor_id=actor["id"],
        actor_type=actor["type"],         # user / service / system
        actor_ip=actor.get("ip"),
        actor_user_agent=actor.get("user_agent"),

        # Risorsa e azione
        resource_type=resource["type"],   # order / payment / user
        resource_id=resource["id"],
        action=action,                    # create / read / update / delete

        # Outcome e tracciabilità
        outcome=outcome,
        trace_id=get_trace_id(),          # Correlazione con i trace distribuiti
        request_id=actor.get("request_id"),

        # Contesto aggiuntivo
        **(context or {}),

        # Campi obbligatori per audit
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        service="orders-service",
        environment="production",
    )

# Utilizzo nei handler
@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, reason: str, user: CurrentUser):
    order = await db.get_order(order_id)

    try:
        await order.cancel(reason=reason)
        log_audit_event(
            "order.cancelled",
            actor={"id": user.id, "type": "user", "ip": request.client.host},
            resource={"type": "order", "id": order_id},
            action="delete",
            outcome="success",
            context={"reason": reason, "previous_status": order.status}
        )
    except PermissionDenied:
        log_audit_event(
            "order.cancel.denied",
            actor={"id": user.id, "type": "user"},
            resource={"type": "order", "id": order_id},
            action="delete",
            outcome="failure",
            context={"reason": "insufficient_permissions"}
        )
        raise
```

**Cosa loggare obbligatoriamente:**
- Ogni operazione di autenticazione (successo e fallimento)
- Ogni operazione su dati sensibili (lettura, modifica, cancellazione)
- Ogni cambio di configurazione o permessi
- Ogni operazione privilegiata (admin actions, sudo equivalents)
- Ogni errore che potrebbe indicare un attacco (rate limit superato, token invalido ripetuto)

---

## Kubernetes Audit Log

Kubernetes ha un sistema di audit built-in che logga ogni richiesta all'API server:

```yaml
# audit-policy.yaml — definisce quali eventi loggare
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
# Log tutte le richieste agli Secrets (livello Request = include request body)
- level: Request
  resources:
  - group: ""
    resources: ["secrets"]

# Log exec e port-forward (eventi critici di sicurezza)
- level: RequestResponse
  resources:
  - group: ""
    resources: ["pods/exec", "pods/portforward", "pods/attach"]

# Log modifiche ai RBAC
- level: RequestResponse
  resources:
  - group: "rbac.authorization.k8s.io"
    resources: ["clusterroles", "clusterrolebindings", "roles", "rolebindings"]

# Log dei namespace ad alta criticità
- level: RequestResponse
  namespaces: ["production", "kube-system"]
  verbs: ["create", "update", "patch", "delete"]

# Read su oggetti di produzione in RequestResponse
- level: Request
  namespaces: ["production"]
  verbs: ["get", "list", "watch"]

# Ometti le richieste non-resourceful non interessanti
- level: None
  users: ["system:kube-proxy"]
  verbs: ["watch"]
  resources:
  - group: ""
    resources: ["endpoints", "services", "services/status"]

# Default: log metadata (timestamp, user, resource) senza il body
- level: Metadata
```

```yaml
# kube-apiserver flags per abilitare audit
# (su EKS/GKE/AKS configurato dalla console/API del provider)
--audit-log-path=/var/log/kubernetes/audit.log
--audit-policy-file=/etc/kubernetes/audit-policy.yaml
--audit-log-maxage=30
--audit-log-maxbackup=10
--audit-log-maxsize=100
```

```bash
# Analisi degli audit log: chi ha fatto exec in produzione?
grep '"verb":"create"' /var/log/kubernetes/audit.log | \
  jq '. | select(.objectRef.subresource == "exec") |
         {user: .user.username, pod: .objectRef.name, ns: .objectRef.namespace, time: .requestReceivedTimestamp}'

# Output:
# {"user": "mario@corp.internal", "pod": "orders-7f9d4b-xyz", "ns": "production", "time": "2024-01-15T14:32:01Z"}
```

---

## Falco — Runtime Security

**[Falco](https://falco.org/)** è il sistema di runtime security di riferimento per Kubernetes, donato alla CNCF. Opera a livello kernel tramite eBPF: intercetta ogni system call e la confronta con un set di regole. Se una regola corrisponde → alert.

La differenza con gli admission controller: Falco monitora il comportamento *durante* l'esecuzione, non al deploy. Rileva attività anomale che potrebbero indicare una compromissione avvenuta a runtime.

```
Container orders-service in produzione

Normale:
  execve("/usr/local/bin/python", ...) → OK
  open("/app/config/settings.json", O_RDONLY) → OK
  connect(8080, "postgres:5432") → OK

ANOMALIA → Falco alert:
  execve("/bin/bash", ...) → ALERT: shell avviata in container
  open("/etc/shadow", ...) → ALERT: accesso a file sistema sensibile
  connect(443, "185.220.101.x") → ALERT: connessione verso Tor exit node
  fork("/bin/nc", "-e", "/bin/sh", ...) → ALERT: netcat con reverse shell
```

```bash
# Installa Falco con Helm
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco \
  --create-namespace \
  --set driver.kind=ebpf \              # eBPF: meno impatto vs kernel module
  --set falcosidekick.enabled=true \    # Forwarding degli alert
  --set falcosidekick.config.slack.webhookurl="$SLACK_WEBHOOK" \
  --set falcosidekick.config.alertmanager.hostport="http://alertmanager:9093"
```

### Regole Falco

```yaml
# /etc/falco/falco_rules.yaml (estratto di regole custom)

# Regola: shell avviata in container (possibile compromissione)
- rule: Shell in Container
  desc: Rilevato avvio di shell in container non di debug
  condition: >
    container and
    proc.name in (shell_binaries) and
    not proc.pname in (shell_binaries) and
    not container.image.repository in (allowed_shell_containers)
  output: >
    Shell avviata in container
    (user=%user.name container=%container.name image=%container.image.repository
     cmdline=%proc.cmdline parent=%proc.pname)
  priority: WARNING
  tags: [container, shell, process]

# Regola: scrittura in directory sistema
- rule: Write Below etc
  desc: Tentativo di scrittura in /etc (modifiche configurazione sistema)
  condition: >
    open_write and
    fd.name startswith /etc and
    not proc.name in (allowed_etc_writers) and
    container
  output: >
    Scrittura sotto /etc (user=%user.name command=%proc.cmdline
     file=%fd.name container=%container.name)
  priority: ERROR

# Regola: accesso alle credenziali Kubernetes
- rule: Read K8s Service Account Token
  desc: Processo che legge il service account token (possibile lateral movement)
  condition: >
    open_read and
    fd.name startswith /run/secrets/kubernetes.io/serviceaccount and
    not proc.name in (k8s_client_binaries)
  output: >
    Lettura SA token
    (user=%user.name proc=%proc.name fd.name=%fd.name container=%container.name)
  priority: WARNING
```

### Falco Sidekick — Alert Routing

```yaml
# falcosidekick configurazione (via Helm values)
config:
  slack:
    webhookurl: "https://hooks.slack.com/services/..."
    minimumpriority: "warning"     # Solo warning e sopra

  alertmanager:
    hostport: "http://alertmanager.monitoring:9093"
    minimumpriority: "error"       # Solo critical/error → AlertManager

  elasticsearch:
    hostport: "http://elasticsearch:9200"
    index: "falco-events"
    minimumpriority: "debug"       # Tutto → Elasticsearch per SIEM

  aws:
    sqs:
      url: "https://sqs.us-east-1.amazonaws.com/123456789/security-events"
    sns:
      topicarn: "arn:aws:sns:us-east-1:123456789:security-alerts"
```

---

## Cloud Audit Logs

I cloud provider hanno il loro sistema di audit nativo — complementare a quello applicativo:

```bash
# AWS CloudTrail — ogni chiamata API AWS
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteSecret \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --query 'Events[*].{Time:EventTime,User:Username,Region:AwsRegion,Resources:Resources}'

# Analisi: chi ha assunto quali IAM role nelle ultime 24h?
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRole \
  --start-time $(date -u -d "24 hours ago" +%Y-%m-%dT%H:%M:%SZ) | \
  jq '.Events[] | {time: .EventTime, user: .Username, role: (.CloudTrailEvent | fromjson | .requestParameters.roleArn)}'

# AWS CloudTrail Lake — SQL query sugli audit log
aws cloudtrail-data start-query \
  --query-statement "SELECT eventTime, userIdentity.arn, eventName, requestParameters
                     FROM $EDS_ID
                     WHERE eventName LIKE '%Delete%'
                     AND eventTime > '2024-01-01'
                     ORDER BY eventTime DESC
                     LIMIT 100"
```

---

## SIEM — Security Information and Event Management

Il SIEM centralizza i log di sicurezza da tutte le sorgenti e applica regole di correlazione per rilevare pattern di attacco:

```yaml
# Esempio architettura SIEM open source con OpenSearch
# Fluentbit raccoglie → OpenSearch indicizza → OpenSearch Dashboards visualizza

# fluentbit-config.yaml
[INPUT]
  Name tail
  Path /var/log/containers/*_production_*.log
  Tag kube.production.*
  Parser containerd

[FILTER]
  Name kubernetes
  Match kube.*
  Kube_URL https://kubernetes.default.svc:443

[FILTER]
  Name grep
  Match kube.*
  Exclude log /health

[OUTPUT]
  Name opensearch
  Match *
  Host opensearch.logging.svc.cluster.local
  Port 9200
  Index security-audit
  Time_Key @timestamp
  Retry_Limit 5
```

```json
// Regola di correlazione OpenSearch Alerting
// Rilevazione brute force: >5 autenticazioni fallite in 5 minuti dallo stesso IP
{
  "name": "Brute Force Detection",
  "type": "monitor",
  "schedule": {"period": {"interval": 5, "unit": "MINUTES"}},
  "inputs": [{
    "search": {
      "indices": ["security-audit*"],
      "query": {
        "size": 0,
        "query": {
          "bool": {
            "filter": [
              {"term": {"event": "auth.login.failure"}},
              {"range": {"@timestamp": {"gte": "now-5m"}}}
            ]
          }
        },
        "aggs": {
          "by_ip": {
            "terms": {"field": "actor_ip", "min_doc_count": 5}
          }
        }
      }
    }
  }],
  "triggers": [{
    "name": "IP with 5+ failures",
    "severity": "3",
    "condition": {
      "script": {"source": "ctx.results[0].aggregations.by_ip.buckets.size() > 0"}
    },
    "actions": [{
      "name": "Alert Slack",
      "destination_id": "slack-webhook-id",
      "message_template": {
        "source": "Brute force rilevato da: {{ctx.results[0].aggregations.by_ip.buckets}}"
      }
    }]
  }]
}
```

---

## Requisiti di Compliance — Overview

| Framework | Log Retention | Requisiti Chiave |
|-----------|---------------|-----------------|
| **SOC 2 Type II** | Min 1 anno | Accesso privilegiato loggato, change management, incident response |
| **ISO 27001** | Definita dalla policy | Audit trail, eventi di sicurezza, review periodica |
| **PCI-DSS v4** | Min 1 anno (12 mesi online) | Log di ogni accesso al cardholder environment, clock sync, log integrity |
| **GDPR** | Proporzionale al trattamento | Accesso ai dati personali tracciabile, diritto alla cancellazione |
| **HIPAA** | Min 6 anni | Audit trail per PHI access, hardware/software/procedure review |

```bash
# Verifica che Kubernetes API server audit sia configurato correttamente (CIS Benchmark)
kube-bench run --targets master --check 1.2.22,1.2.23,1.2.24

# CIS Benchmark Kubernetes
# [PASS] 1.2.22 Ensure that the --audit-log-path argument is set
# [PASS] 1.2.23 Ensure that the --audit-log-maxage argument is set to 30 or as appropriate
# [FAIL] 1.2.24 Ensure that the --audit-log-maxsize argument is set to 100 or as appropriate
```

---

## Best Practices

- **Immutabilità dei log**: i log non devono poter essere modificati — usare storage append-only (S3 con Object Lock, Worm storage, log forwarding immediato verso SIEM esterno). Un attacker che compromette il sistema può cancellare le prove se i log sono modificabili
- **Clock synchronization**: tutti i sistemi devono usare NTP sincronizzato — log con timestamp discordanti sono inutilizzabili per correlazione e invalidi per compliance (PCI-DSS esplicito su questo)
- **Log structured, non free-text**: i log in formato JSON permettono query, alerting e correlazione automatica. I log in formato testo richiedono parsing fragile e sono inutili come SIEM input
- **Separazione: chi logga non può cancellare**: il service account che scrive i log non deve avere permessi di delete sullo storage dei log — separation of duties
- **Falco DryRun prima della produzione**: le prime versioni delle regole Falco producono falsi positivi. Usare `output_fields` e validare su staging prima di collegare alert bloccanti

## Riferimenti

- [Falco Documentation](https://falco.org/docs/)
- [Kubernetes Audit Logging](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)
- [OpenSearch Security Analytics](https://opensearch.org/docs/latest/security-analytics/)
- [AWS CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [OWASP Logging Cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
