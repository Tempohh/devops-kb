---
title: "Falco — Runtime Threat Detection"
slug: falco
category: security
tags: [falco, runtime-security, threat-detection, kubernetes-security, ebpf, syscall-monitoring, siem, daemonset]
search_keywords: [falco, falco runtime, falco kubernetes, falco ebpf, falco rules, falco sidekick, falcosidekick, runtime threat detection, syscall monitoring, behavioral security, container security, kubernetes security monitoring, cloud-native security, CNCF falco, runtime anomaly detection, falco driver, falco engine, falco alerts, threat detection k8s, falco helm, falco operator, falco rules engine, runtime intrusion detection, IDS container, container IDS, falco macro, falco list, falco exceptions, kernel driver security, eBPF security, security observability, MITRE ATT&CK container, falco output, falco priority, falco conditions, falco fields]
parent: security/runtime/_index
related: [security/runtime/seccomp-apparmor, security/supply-chain/admission-control, containers/kubernetes/sicurezza, monitoring/alerting/alertmanager]
official_docs: https://falco.org/docs/
status: complete
difficulty: advanced
last_updated: 2026-04-04
---

# Falco — Runtime Threat Detection

## Panoramica

**Falco** è il tool open source standard de facto per il **runtime threat detection** nei cluster Kubernetes e negli ambienti container. Sviluppato da Sysdig e donato alla CNCF (graduated project), Falco osserva il comportamento dei workload a livello di kernel intercettando le system call e valutando in tempo reale una serie di regole configurabili.

A differenza di seccomp e AppArmor che **prevengono** azioni non autorizzate bloccandole, Falco **rileva** e **segnala** comportamenti anomali: un container che esegue una shell, un processo che legge `/etc/shadow`, una connessione verso IP C2. Questa differenza è fondamentale: Falco non blocca, ma osserva e allerta — permettendo anche di rilevare attività legittime ma anomale che i meccanismi preventivi non catturano.

| Caratteristica | Falco | seccomp/AppArmor |
|---|---|---|
| Approccio | Detection (rileva e allerta) | Prevention (blocca prima) |
| Reazione | Alert → SIEM/Slack/PagerDuty | Blocco diretto dell'azione |
| Configurabilità regole | Alta: YAML human-readable | Bassa: formato binario/profilo |
| Visibilità | Logging contestuale ricco | Solo blocco/allow |
| Impatto performance | Basso (eBPF) | Molto basso (in-kernel BPF) |
| Pattern consigliato | Complementare a seccomp/AppArmor | Complementare a Falco |

Falco è il componente di **detection** in una strategia defense-in-depth: seccomp/AppArmor riducono la superficie di attacco, Falco rileva quando qualcosa sfugge comunque.

!!! warning "Falco rileva, non blocca"
    Per default Falco non blocca nulla — emette alert. Per risposta automatica (terminare un pod, isolare un namespace) occorre integrare Falco con un sistema di risposta come Falco Talon o script custom via Falco Sidekick webhook. Pianifica sempre il workflow di risposta agli alert prima di andare in produzione.

---

## Architettura

### Componenti Principali

```
┌─────────────────────────────────────────────────────────────┐
│                        Nodo Kubernetes                       │
│                                                             │
│  ┌─────────────┐    syscall events    ┌──────────────────┐  │
│  │  Workloads  │ ──────────────────▶  │  Kernel Driver   │  │
│  │  (Pod/Cont) │                      │  (eBPF o kmod)   │  │
│  └─────────────┘                      └────────┬─────────┘  │
│                                                │             │
│                                      ┌─────────▼──────────┐ │
│                                      │   Falco Engine     │ │
│                                      │  (userspace)       │ │
│                                      │  ┌──────────────┐  │ │
│                                      │  │ Rules Engine │  │ │
│                                      │  │ (conditions) │  │ │
│                                      │  └──────┬───────┘  │ │
│                                      └─────────┼──────────┘ │
│                                                │ alert       │
│                                      ┌─────────▼──────────┐ │
│                                      │  Falco Sidekick    │ │
│                                      │  (fan-out output)  │ │
│                                      └─────────┬──────────┘ │
└────────────────────────────────────────────────┼────────────┘
                                                 │
                        ┌────────────────────────┼───────────────┐
                        ▼            ▼            ▼               ▼
                     Slack      Elasticsearch  PagerDuty    Custom SIEM
```

### Kernel Driver: eBPF vs Kernel Module

Falco intercetta le system call tramite uno di questi driver:

| Driver | Pro | Contro | Quando usare |
|---|---|---|---|
| **eBPF** (`driver.kind=ebpf`) | No compilazione, sicuro, stabile | Richiede kernel 4.14+ | **Raccomandato** per la maggior parte dei cluster |
| **Modern eBPF** (`driver.kind=modern-bpf`) | Integrato nel kernel (CO-RE), nessuna dipendenza | Richiede kernel 5.8+ | Cluster con kernel recenti (EKS 1.27+, GKE) |
| **Kernel Module** (`driver.kind=kmod`) | Massima compatibilità | Richiede compilazione, rischio stabilità | Kernel vecchi o ambienti air-gapped |

Il driver eBPF è il tipo di installazione consigliato: non richiede la compilazione di moduli kernel, funziona con la maggior parte delle distribuzioni managed (EKS, GKE, AKS) e non presenta rischi di instabilità del nodo.

### Falco Engine

Il **Falco Engine** gira in userspace e riceve il flusso di eventi dal driver kernel. Per ogni evento:

1. Valuta le `conditions` delle regole attive (espressioni booleane sui campi dell'evento)
2. Se una condizione è vera → genera un alert con il template `output` della regola
3. L'alert include campi contestuali: container, processo, utente, syscall, timestamp
4. L'alert viene inviato agli output configurati (stdout, file, gRPC, Falco Sidekick)

### Falco Sidekick

**Falco Sidekick** è il componente opzionale che riceve gli alert dal Falco Engine e li distribuisce verso destinazioni multiple:

- Slack, Teams, Discord
- Elasticsearch, OpenSearch, Splunk
- PagerDuty, OpsGenie
- AWS SNS/SQS, Lambda
- Webhook generico (per SIEM proprietari)
- Grafana Loki (per correlazione con log)

Sidekick permette di filtrare gli alert per `minimumpriority` verso ogni destinazione — ad esempio mandare solo `CRITICAL` a PagerDuty e tutto da `WARNING` a Elasticsearch.

---

## Installazione via Helm

### Deploy Base con eBPF e Sidekick

```bash
# Aggiungi il repository Helm Falco
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo update

# Installa Falco con eBPF driver e Sidekick abilitato
helm install falco falcosecurity/falco \
  --namespace falco \
  --create-namespace \
  --set driver.kind=ebpf \
  --set falcosidekick.enabled=true \
  --set falcosidekick.webui.enabled=true \
  --set falcosidekick.config.slack.webhookurl="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX" \
  --set falcosidekick.config.slack.minimumpriority="warning"

# Verifica che i pod girino su tutti i nodi (DaemonSet)
kubectl get pods -n falco -o wide
# NAME                           READY   STATUS    NODE
# falco-8xk2p                    2/2     Running   node-1
# falco-9mhzr                    2/2     Running   node-2
# falco-sidekick-7f9b4d5-qxkmp   1/1     Running   node-1
```

```bash
# Verifica che Falco stia raccogliendo eventi
kubectl logs -n falco -l app.kubernetes.io/name=falco -c falco --tail=50

# Output atteso all'avvio:
# {"hostname":"node-1","level":"notice","msg":"Falco version: 0.38.1",
#  "rule":"","time":"2026-04-04T10:00:00.000000000Z"}
# {"hostname":"node-1","level":"notice","msg":"Loading rules file /etc/falco/falco_rules.yaml",
#  "rule":"","time":"2026-04-04T10:00:00.000000001Z"}
# {"hostname":"node-1","level":"notice","msg":"Enabled rules: 150 (out of 300 total)",
#  "rule":"","time":"2026-04-04T10:00:00.000000002Z"}
```

### Values.yaml per Produzione

```yaml
# falco-values.yaml — configurazione production
driver:
  kind: ebpf   # Raccomandato: no kernel module compilation

# Falco engine settings
falco:
  # Riduci l'output verbose di default
  json_output: true
  json_include_output_property: true
  log_level: warning
  priority: warning   # Ignora eventi DEBUG/INFO/NOTICE

  # Custom rules directory
  rules_files:
    - /etc/falco/falco_rules.yaml           # Regole ufficiali built-in
    - /etc/falco/falco_rules.local.yaml     # Override/aggiunte custom
    - /etc/falco/rules.d/*.yaml             # Regole custom da ConfigMap

  # Output: stdout + gRPC (per Sidekick)
  stdout_output:
    enabled: true
  grpc:
    enabled: true
    bind_address: "unix:///run/falco/falco.sock"
  grpc_output:
    enabled: true

# Monta regole custom da ConfigMap
extra:
  initContainers: []

falcoctl:
  artifact:
    install:
      enabled: true
    follow:
      enabled: true

# Falco Sidekick
falcosidekick:
  enabled: true
  replicaCount: 2   # HA per non perdere alert
  
  config:
    # Elasticsearch (SIEM primario)
    elasticsearch:
      hostport: "https://elasticsearch.monitoring.svc.cluster.local:9200"
      index: "falco-alerts"
      username: "falco"
      password: "CHANGEME"   # Usa un secret Kubernetes, non inline
      minimumpriority: "debug"  # Tutti gli alert verso ES

    # Slack (alert operativi)
    slack:
      webhookurl: "https://hooks.slack.com/services/..."
      channel: "#security-alerts"
      minimumpriority: "warning"   # Solo WARNING e sopra
      messageformat: "Alert Falco: rule={rule} priority={priority} container={container.name}"

    # PagerDuty (alert critici)
    pagerduty:
      routingkey: "R1234567890abcdef"
      minimumpriority: "critical"   # Solo CRITICAL/EMERGENCY/ALERT

  webui:
    enabled: true
    replicaCount: 1
```

```bash
# Applica la configurazione
helm upgrade --install falco falcosecurity/falco \
  --namespace falco \
  --create-namespace \
  --values falco-values.yaml

# Test: genera un evento manualmente
kubectl exec -it -n default some-pod -- bash
# Questo deve generare l'alert "Terminal shell in container"

# Verifica l'alert nei log di Sidekick
kubectl logs -n falco -l app.kubernetes.io/name=falcosidekick --tail=20
```

---

## Rules — Struttura e Custom Rules

### Anatomia di una Regola

```yaml
# Struttura completa di una regola Falco
- rule: Spawn Shell in Container
  desc: Un processo shell è stato avviato in un container in esecuzione
  condition: >
    container.id != host
    and proc.name in (shell_binaries)
    and container.privileged = false
    and not proc.pname in (container_entrypoints)
  output: >
    Shell spawned in container
    (user=%user.name user_loginuid=%user.loginuid
     container=%container.name image=%container.image.repository:%container.image.tag
     shell=%proc.name parent=%proc.pname cmdline=%proc.cmdline
     pid=%proc.pid k8s_ns=%k8s.ns.name k8s_pod=%k8s.pod.name)
  priority: WARNING
  tags: [container, shell, mitre_execution, T1059]
```

Campi obbligatori:

| Campo | Descrizione |
|---|---|
| `rule` | Nome univoco della regola |
| `desc` | Descrizione human-readable |
| `condition` | Espressione booleana sui campi Falco |
| `output` | Template del messaggio di alert (con interpolazione `%field`) |
| `priority` | Livello di severità |

### Livelli di Priority

```
EMERGENCY   → Sistema inutilizzabile (exploit attivo, kernel compromise)
ALERT       → Azione immediata richiesta (container escape attempt)
CRITICAL    → Condizione critica (privilege escalation, C2 communication)
ERROR       → Errore che richiede attenzione
WARNING     → Comportamento anomalo da investigare (shell in container, read /etc/passwd)
NOTICE      → Evento normale ma significativo
INFO        → Evento informativo
DEBUG       → Debug verboso
```

### Campi Falco Principali

```yaml
# Campi processo
proc.name          # Nome del processo (es. bash, python3)
proc.pname         # Nome del processo padre
proc.cmdline       # Command line completa
proc.pid           # PID del processo
proc.exe           # Path dell'eseguibile
proc.exepath       # Path assoluto dell'eseguibile
proc.args          # Argomenti del processo

# Campi utente
user.name          # Nome utente
user.uid           # UID
user.loginuid      # UID di login (auid)

# Campi container
container.id       # ID container (o "host" per processi host)
container.name     # Nome container
container.image.repository  # Registry/image (es. nginx)
container.image.tag         # Tag immagine
container.privileged        # true se privileged mode

# Campi Kubernetes
k8s.ns.name        # Namespace Kubernetes
k8s.pod.name       # Nome pod
k8s.deployment.name        # Nome deployment
k8s.daemonset.name         # Nome daemonset

# Campi file/fd
fd.name            # Path file o indirizzo socket
fd.typechar        # Tipo fd: f(file), 4(IPv4), 6(IPv6), u(unix)

# Campi rete
fd.sip             # Source IP
fd.dip             # Destination IP
fd.sport           # Source port
fd.dport           # Destination port
fd.l4proto         # Protocollo (tcp, udp)
```

### Liste e Macro — Riutilizzo Condizioni

```yaml
# Liste: insiemi di valori riutilizzabili
- list: shell_binaries
  items: [bash, sh, zsh, ksh, fish, tcsh, csh, dash]

- list: sensitive_files
  items:
    - /etc/shadow
    - /etc/passwd
    - /etc/sudoers
    - /root/.ssh/authorized_keys
    - /root/.bash_history

- list: trusted_images
  items:
    - my-company/debug-tools
    - my-company/monitoring-agent

# Macro: condizioni booleane riutilizzabili
- macro: container
  condition: container.id != host

- macro: interactive
  condition: >
    proc.stdin_type in (tty, file, pipe)
    and proc.stdout_type in (tty, file, pipe)

- macro: spawned_process
  condition: evt.type = execve and evt.dir = <

- macro: never_true
  condition: evt.num = 0

# Uso nelle regole
- rule: Interactive Shell in Container
  desc: Shell interattiva avviata in container (segnala accesso manuale)
  condition: >
    container
    and spawned_process
    and interactive
    and proc.name in (shell_binaries)
  output: >
    Interactive shell in container
    (user=%user.name container=%container.name image=%container.image.repository
     cmd=%proc.cmdline k8s_pod=%k8s.pod.name)
  priority: NOTICE
  tags: [container, shell, access]
```

---

## Regole Built-in Più Importanti

Falco include circa 150 regole predefinite. Le più importanti per ambienti Kubernetes:

```yaml
# Le regole seguenti sono già presenti in falco_rules.yaml (built-in)
# Non è necessario dichiararle — sono attive per default

# 1. Terminal shell in container
# Rileva: kubectl exec -it pod -- bash
- rule: Terminal shell in container
  condition: >
    container and
    shell_procs and proc.tty != 0 and container_entrypoint
  priority: NOTICE
  tags: [container, shell, T1059]

# 2. Accesso anomalo all'API Server K8s
# Rileva: curl https://kubernetes.default.svc dall'interno di un pod
- rule: Contact K8S API Server From Container
  condition: >
    evt.type = connect and
    container and
    not k8s_containers and
    fd.typechar = 4 and fd.sip.name contains "kubernetes.default"
  priority: NOTICE
  tags: [network, k8s, T1552]

# 3. Lettura file sensibili
# Rileva: cat /etc/shadow, cat /etc/passwd da container
- rule: Read sensitive file untrusted
  condition: >
    sensitive_files and
    open_read and
    container and
    not proc.name in (sensitive_file_access_procs)
  priority: WARNING
  tags: [filesystem, T1552, credential-access]

# 4. Scrittura fuori dai path previsti
# Rileva: creazione file in / o in /etc, /usr, /bin
- rule: Write below root
  condition: >
    root_dir and
    open_write and
    not proc.name in (known_root_files_writers)
  priority: ERROR
  tags: [filesystem, T1565]

# 5. Privilege escalation via setuid
# Rileva: proc.suid=root o cambiamento capabilities
- rule: Drop and execute new binary in container
  condition: >
    spawned_process and
    container and
    proc.is_exe_upper_layer=true
  priority: CRITICAL
  tags: [container, T1059, T1068]

# 6. Connessione a server C2
# Rileva: connessioni in uscita verso threat intel feed di IP noti
- rule: Outbound Connection to C2 Servers
  condition: >
    outbound and
    fd.sip in (c2_server_ip_list)
  priority: CRITICAL
  tags: [network, c2, T1071]
```

---

## Falco Sidekick — Integrazione SIEM e Alerting

### Configurazione Avanzata Output

```yaml
# falco-sidekick-config.yaml — ConfigMap per configurazione avanzata
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-sidekick-config
  namespace: falco
data:
  config.yaml: |
    listenaddress: "0.0.0.0"
    listenport: 2801

    # Elasticsearch: tutti gli alert per analisi SIEM
    elasticsearch:
      hostport: "https://elasticsearch.monitoring.svc:9200"
      index: "falco"
      type: "_doc"
      username: "falco-writer"
      password: "${ELASTICSEARCH_PASSWORD}"   # env var da Secret
      minimumpriority: "debug"
      checkcert: true
      mutualtls: false

    # Slack: alert warning+ con formato custom
    slack:
      webhookurl: "${SLACK_WEBHOOK_URL}"
      footer: "Falco Runtime Security"
      icon: ":rotating_light:"
      minimumpriority: "warning"
      messageformat: >
        *[{priority}]* Rule: `{rule}`
        Container: `{container.name}` | Pod: `{k8s.pod.name}` | NS: `{k8s.ns.name}`
        Command: `{proc.cmdline}`

    # PagerDuty: solo critical e sopra
    pagerduty:
      routingkey: "${PAGERDUTY_ROUTING_KEY}"
      minimumpriority: "critical"

    # Loki: per correlazione con log applicativi
    loki:
      hostport: "http://loki.monitoring.svc:3100"
      tenant: ""
      minimumpriority: "warning"
      customHeaders:
        X-Scope-OrgID: "falco"

    # Webhook generico per automazione risposta
    webhook:
      address: "http://falco-responder.security.svc:8080/alert"
      minimumpriority: "critical"
      checkcert: false

    customfields:
      environment: "production"
      cluster: "eks-prod-eu-west-1"
```

```bash
# Applica la ConfigMap e riavvia Sidekick
kubectl apply -f falco-sidekick-config.yaml
kubectl rollout restart deployment/falco-falcosidekick -n falco

# Test del webhook Sidekick
curl -s http://falco-falcosidekick.falco.svc:2801/test
# {"message":"OK"}

# Invia un test alert manuale
curl -s -X POST http://falco-falcosidekick.falco.svc:2801/ \
  -H "Content-Type: application/json" \
  -d '{"output":"Test alert from Falco","priority":"warning","rule":"Test Rule"}'
```

---

## Tuning e Riduzione Falsi Positivi

Falco out-of-the-box genera molti falsi positivi in ambienti reali. Il tuning è obbligatorio prima del go-live in produzione.

### Approccio con Exceptions (Raccomandato)

```yaml
# falco_rules.local.yaml — Personalizzazioni locali
# Questo file viene caricato DOPO le regole built-in e può override qualsiasi regola

# METODO 1: Exceptions per whitelist specifiche
# Whitelista container di debug autorizzati dalla regola "Spawn Shell in Container"
- rule: Terminal shell in container
  exceptions:
    - name: authorized_debug_containers
      fields: [container.image.repository, k8s.ns.name]
      values:
        - [my-company/debug-tools, debug]
        - [my-company/ops-toolbox, ops]
    - name: ci_build_containers
      fields: [container.image.repository]
      values:
        - [jenkins/agent]
        - [gitlab/gitlab-runner-helper]

# METODO 2: Override completo della condition con append
# Estendi la condizione built-in senza ridefinire tutta la regola
- rule: Read sensitive file untrusted
  condition: and not (k8s.ns.name = "vault" and container.image.repository = "vault")
  append: true

# METODO 3: Disabilita completamente una regola (usare con cautela)
- rule: Contact K8S API Server From Container
  enabled: false
  # Solo se hai un agent legittime che accede all'API server (es. kube-state-metrics custom)

# METODO 4: Nuova macro per escludere namespace di sistema
- macro: excluded_namespaces
  condition: k8s.ns.name in (kube-system, kube-public, falco, monitoring, cert-manager)

# Usa la macro nelle regole personalizzate
- rule: Unexpected Outbound Network Connection
  desc: Rileva connessioni di rete verso destinazioni non attese
  condition: >
    container and
    outbound and
    not excluded_namespaces and
    not fd.dip in (allowed_external_ips) and
    not fd.dport in (allowed_external_ports)
  output: >
    Unexpected outbound connection
    (container=%container.name image=%container.image.repository
     dst=%fd.dip dport=%fd.dport proto=%fd.l4proto
     pod=%k8s.pod.name ns=%k8s.ns.name)
  priority: WARNING
  tags: [network, custom]
```

### Deploy Custom Rules via ConfigMap

```yaml
# ConfigMap per regole custom — montato come volume nel DaemonSet Falco
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-custom-rules
  namespace: falco
data:
  custom_rules.yaml: |
    # Regole specifiche per il tuo ambiente
    - list: internal_trusted_ips
      items:
        - "10.0.0.0/8"
        - "172.16.0.0/12"
        - "192.168.0.0/16"

    - macro: internal_network
      condition: fd.dip in (internal_trusted_ips)

    - rule: Cryptocurrency Mining Detection
      desc: Rileva processi tipici di cryptomining (xmrig, minergate, etc.)
      condition: >
        container and
        spawned_process and
        (proc.name in (crypto_miners) or
         proc.cmdline contains "stratum+" or
         proc.cmdline contains "xmrig" or
         proc.cmdline contains "--algo")
      output: >
        Cryptomining detected in container
        (container=%container.name image=%container.image.repository
         proc=%proc.name cmd=%proc.cmdline pod=%k8s.pod.name)
      priority: CRITICAL
      tags: [cryptomining, T1496, custom]

    - list: crypto_miners
      items: [xmrig, minerd, cpuminer, cgminer, bfgminer, ethminer]
```

```yaml
# Helm values.yaml: monta la ConfigMap come volume
falco:
  extraVolumes:
    - name: custom-rules
      configMap:
        name: falco-custom-rules
  extraVolumeMounts:
    - name: custom-rules
      mountPath: /etc/falco/rules.d
      readOnly: true
```

---

## Confronto con seccomp/AppArmor

Falco, seccomp e AppArmor rispondono a problemi diversi e sono complementari:

| Aspetto | seccomp | AppArmor | Falco |
|---|---|---|---|
| **Tipo** | Prevention | Prevention | Detection |
| **Livello** | Syscall (kernel) | LSM (kernel) | Userspace observer |
| **Azione** | Blocca syscall | Blocca accesso file/rete | Emette alert |
| **Configurazione** | JSON + allowlist syscall | Profilo LSM | Regole YAML human-readable |
| **Visibilità** | Nessuna (blocco silenzioso) | Audit log opzionale | Alert ricchi con contesto K8s |
| **Overhead** | ~0.3% | ~0.5% | ~1-3% (eBPF) |
| **Granularità** | Per syscall | Per path/capability | Per evento (proc, net, file) |

**Pattern architetturale consigliato:**

```
┌────────────────────────────────────────────────────────┐
│                  Defense in Depth                       │
│                                                         │
│  1. Admission Control (Kyverno/OPA)                     │
│     └▶ Impedisce deploy non conformi                    │
│                                                         │
│  2. seccomp (RuntimeDefault)                            │
│     └▶ Riduce la superficie di syscall disponibili      │
│                                                         │
│  3. AppArmor (profilo per workload)                     │
│     └▶ Limita accesso a file, rete, capabilities        │
│                                                         │
│  4. Falco (DaemonSet su tutti i nodi)                   │
│     └▶ Rileva comportamenti anomali che sfuggono        │
│        ai controlli preventivi                          │
└────────────────────────────────────────────────────────┘
```

!!! tip "Inizia con Falco in detection-only"
    Nelle fasi iniziali, abilita Falco con le regole built-in in modalità detection (alert solo, nessun blocco). Questo ti permette di capire il comportamento reale dei tuoi workload prima di applicare controlli preventivi. Dopo 2-4 settimane di osservazione, userai i dati Falco per costruire profili seccomp/AppArmor accurati.

---

## Best Practices

- **Driver eBPF sempre**: evita il kernel module in produzione — richiede compilazione specifica per la versione kernel del nodo e può destabilizzare il sistema.
- **DaemonSet su tutti i nodi**: Falco deve girare su ogni nodo senza eccezioni. Usa `tolerations: - operator: Exists` per includerlo anche sui nodi master/control-plane.
- **Falco Sidekick in HA**: almeno 2 repliche di Sidekick con `replicaCount: 2`. Un singolo Sidekick è un SPOF che causa perdita di alert.
- **Tuning prima del go-live**: le regole built-in generano 50-200 falsi positivi/ora in un cluster tipico. Dedica una settimana al tuning prima di connettere PagerDuty.
- **Separa regole in file distinti**: mantieni `falco_rules.yaml` (built-in, non modificare) + `falco_rules.local.yaml` (tue customizzazioni). Questo facilita gli upgrade delle regole ufficiali.
- **Monitora la health di Falco stesso**: usa le metriche Prometheus di Falco (`/metrics`) per rilevare se il driver eBPF è crashato o se l'engine non processa eventi.
- **Versiona le regole custom**: tieni le regole custom in Git e deployale via GitOps (ConfigMap gestita da ArgoCD/Flux). Non modificare le regole direttamente sui nodi.

!!! warning "Non usare Falco come unico controllo di sicurezza"
    Falco può essere bypassato: un attaccante con accesso root al nodo può fermare il DaemonSet Falco prima di compiere azioni malevole. Falco è uno strato di detection, non il solo controllo. Integra sempre con admission control preventivo e auditing Kubernetes.

!!! tip "Falco Talon per risposta automatica"
    **Falco Talon** (CNCF project) permette di definire risposte automatiche agli alert Falco: terminare un pod, applicare una NetworkPolicy, isolare un namespace. Configuralo con cautela — la risposta automatica aggressiva può causare outage in caso di falsi positivi.

---

## Troubleshooting

### 1. Falco non avvia — driver eBPF non compatibile

**Sintomo:**
```
Error: failed to load eBPF program: error while loading program: invalid argument
```
o il pod Falco va in `CrashLoopBackOff` con log:
```
eBPF probe failed to load: probe not found for kernel version 5.4.0-150-generic
```

**Causa:** Il kernel del nodo non supporta il tipo eBPF selezionato, oppure la versione di Falco non ha una probe pre-compilata per questo kernel.

**Soluzione:**
```bash
# Verifica la versione kernel del nodo
kubectl get node node-1 -o jsonpath='{.status.nodeInfo.kernelVersion}'
# 5.4.0-150-generic

# Opzione 1: prova con modern-bpf (richiede kernel 5.8+)
helm upgrade falco falcosecurity/falco \
  --namespace falco \
  --reuse-values \
  --set driver.kind=modern-bpf

# Opzione 2: fallback al kernel module (meno raccomandato)
helm upgrade falco falcosecurity/falco \
  --namespace falco \
  --reuse-values \
  --set driver.kind=kmod \
  --set driver.loader.initContainer.enabled=true

# Verifica il tipo di driver attivo
kubectl exec -n falco falco-XXXXX -- falco --version
# Falco version: 0.38.1 (x86_64)
# Driver version: ...
# Driver type: ebpf
```

### 2. Troppi falsi positivi — alert storm su Slack

**Sintomo:** Slack viene inondato da centinaia di alert al minuto, principalmente da namespace di sistema o da agent di monitoraggio.

**Causa:** Le regole built-in Falco non conoscono il tuo ambiente specifico. Tool come `prometheus-node-exporter`, `datadog-agent`, `fluent-bit` accedono a file e processi che triggherano le regole built-in.

**Soluzione:**
```bash
# 1. Identifica le top regole che generano più alert
kubectl logs -n falco -l app.kubernetes.io/name=falco -c falco | \
  grep '"rule"' | \
  jq -r '.rule' | \
  sort | uniq -c | sort -rn | head -20
# 245 Read sensitive file untrusted
# 189 Write below etc
#  97 Contact K8S API Server From Container
# ...

# 2. Per ogni regola ad alto volume, identifica i source container
kubectl logs -n falco -l app.kubernetes.io/name=falco -c falco | \
  jq 'select(.rule == "Read sensitive file untrusted") | .output_fields' | \
  jq -r '."container.image.repository"' | \
  sort | uniq -c | sort -rn | head -10
# 180 datadog/agent
#  45 prometheus/node-exporter
# ...

# 3. Aggiungi exceptions per i container legittimi
# In falco_rules.local.yaml:
cat >> /tmp/falco-exceptions.yaml << 'EOF'
- rule: Read sensitive file untrusted
  exceptions:
    - name: monitoring_agents
      fields: [container.image.repository]
      values:
        - [datadog/agent]
        - [prom/node-exporter]
        - [fluent/fluent-bit]
EOF

kubectl create configmap falco-local-rules \
  --from-file=falco_rules.local.yaml=/tmp/falco-exceptions.yaml \
  -n falco --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart daemonset/falco -n falco
```

### 3. Alert Falco non arrivano su Slack

**Sintomo:** Falco genera eventi (visibili nei log del pod), ma Slack non riceve nessun messaggio.

**Causa:** Configurazione errata di Sidekick, webhook URL non valido, o `minimumpriority` troppo alto.

**Soluzione:**
```bash
# 1. Verifica che Sidekick riceva gli eventi da Falco
kubectl logs -n falco -l app.kubernetes.io/name=falcosidekick --tail=50
# [INFO] : Falco Client [OK] | IP:10.0.0.5 Port:5060
# [ERROR] : Slack - Post "https://hooks.slack.com/...": dial tcp: no such host

# 2. Test del webhook Slack direttamente da Sidekick
kubectl exec -n falco deploy/falco-falcosidekick -- \
  curl -s -X POST "https://hooks.slack.com/services/..." \
  -H 'Content-type: application/json' \
  --data '{"text":"Test da Falco Sidekick"}'

# 3. Abbassa temporaneamente il minimumpriority per test
helm upgrade falco falcosecurity/falco \
  --namespace falco \
  --reuse-values \
  --set "falcosidekick.config.slack.minimumpriority=debug"

# 4. Genera un evento di test
kubectl exec -n default $(kubectl get pod -o name | head -1) -- id
# Questo dovrebbe generare almeno un NOTICE

# 5. Verifica la configurazione Sidekick corrente
kubectl exec -n falco deploy/falco-falcosidekick -- \
  cat /etc/falcosidekick/config.yaml | grep -A5 slack
```

### 4. Falco consuma troppa CPU

**Sintomo:** Il pod Falco usa >20% CPU continuamente, impattando i workload sul nodo.

**Causa:** Volume eccessivo di eventi kernel processati, spesso dovuto a regole che matchano troppo frequentemente o a workload molto attivi (database, streaming).

**Soluzione:**
```bash
# 1. Misura il volume di eventi per regola
kubectl exec -n falco falco-XXXXX -- \
  cat /var/run/falco/falco_stats.json | jq '.rules | to_entries | sort_by(-.value.matched) | .[0:10]'

# 2. Aumenta la priority minima per ridurre l'elaborazione
# In falco values.yaml:
# falco:
#   priority: warning  # Ignora DEBUG/INFO/NOTICE (riduce ~40% degli eventi)

# 3. Disabilita regole ad alto overhead su namespace non critici
# Usa la condition: and not k8s.ns.name in (high-traffic-ns)

# 4. Limita le risorse con priority class per non impattare workload critici
# (il pod Falco con priorityClassName: system-node-critical è già il default Helm)

# 5. Monitora le metriche Falco
kubectl port-forward -n falco daemonset/falco 8765:8765
curl -s http://localhost:8765/metrics | grep falco_events_processed_total
```

---

## Relazioni

Falco si integra con gli altri meccanismi di sicurezza runtime della KB:

??? info "seccomp e AppArmor — Prevenzione Complementare"
    Falco è la componente di detection della triade runtime security. seccomp filtra le syscall disponibili (riduce la superficie), AppArmor limita accesso a file e rete. Falco osserva ciò che succede nonostante questi controlli. I tre operano in modo complementare: seccomp/AppArmor prevengono, Falco rileva i bypass e le azioni anomale ancora permesse.

    **Approfondimento →** [seccomp e AppArmor](seccomp-apparmor.md)

??? info "Admission Control — Prevenzione al Deploy"
    Kyverno e OPA Gatekeeper agiscono al momento del deploy, non a runtime. Falco copre il gap temporale: anche se un workload viene deployato correttamente, il suo comportamento a runtime può evolvere (vulnerability exploit, misconfiguration exploitation). I due layer sono complementari per profondità temporale.

    **Approfondimento →** [Admission Control](../supply-chain/admission-control.md)

??? info "Kubernetes Sicurezza — SecurityContext e RBAC"
    Il `securityContext` del pod (runAsNonRoot, readOnlyRootFilesystem, capabilities) riduce ulteriormente il blast radius in caso di compromissione. Falco monitora i tentativi di violare questi vincoli a runtime. RBAC limita cosa i processi possono fare tramite API K8s; Falco monitora le chiamate anomale all'API server.

    **Approfondimento →** [Kubernetes Sicurezza](../../containers/kubernetes/sicurezza.md)

??? info "Alertmanager — Routing degli Alert"
    Per cluster con Prometheus Operator, Falco Sidekick può inviare alert a Alertmanager (via webhook), che poi li instrada secondo le sue route policies. Questo centralizza il routing degli alert di sicurezza insieme agli alert infrastrutturali, permettendo silencing, grouping e escalation coerenti.

    **Approfondimento →** [Alertmanager](../../monitoring/alerting/alertmanager.md)

---

## Riferimenti

- [Falco — Documentazione ufficiale](https://falco.org/docs/)
- [Falco — Regole built-in (GitHub)](https://github.com/falcosecurity/rules)
- [Falco Sidekick — Documentazione](https://github.com/falcosecurity/falcosidekick)
- [Falco Sidekick UI](https://github.com/falcosecurity/falcosidekick-ui)
- [Falco Talon — Automated Response](https://github.com/falcosecurity/falco-talon)
- [Falco — Helm Chart](https://github.com/falcosecurity/charts)
- [CNCF — Falco Project](https://www.cncf.io/projects/falco/)
- [MITRE ATT&CK — Container Techniques](https://attack.mitre.org/matrices/enterprise/containers/)
- [Sysdig — Falco Fields Reference](https://falco.org/docs/reference/rules/supported-fields/)
