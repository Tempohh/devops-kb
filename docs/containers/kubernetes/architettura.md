---
title: "Architettura Kubernetes"
slug: architettura
category: containers
tags: [kubernetes, control-plane, etcd, api-server, scheduler, controller-manager, kubelet, kube-proxy]
search_keywords: [kubernetes architecture deep dive, kubernetes control plane components, etcd kubernetes, kube-apiserver, kube-scheduler, kube-controller-manager, cloud-controller-manager, kubelet, kube-proxy, kubernetes request lifecycle, watch mechanism kubernetes, informer kubernetes, leader election kubernetes]
parent: containers/kubernetes/_index
related: [containers/kubernetes/workloads, containers/kubernetes/operators-crd]
official_docs: https://kubernetes.io/docs/concepts/overview/components/
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Architettura Kubernetes

## Il Control Plane — Cervello del Cluster

```
Kubernetes Architecture

  CONTROL PLANE (master nodes)
  +------------------------------------------------------------+
  |                                                            |
  |  kube-apiserver     etcd           kube-scheduler         |
  |  +-----------+     +------+        +--------------+       |
  |  | REST API  |<--->| Raft |        | Watch API    |       |
  |  | Auth/Authz|     | DB   |        | Scoring      |       |
  |  | Admission |     | (3-5 |        | Binding      |       |
  |  | Webhook   |     | nodes)|       +--------------+       |
  |  +-----------+     +------+                               |
  |        ^                           kube-controller-manager|
  |        |                           +--------------+       |
  |        |                           | Node Ctrl    |       |
  |        |                           | Deployment   |       |
  |        |                           | ReplicaSet   |       |
  |        |                           | Job/CronJob  |       |
  |        |                           | Namespace    |       |
  |        |                           +--------------+       |
  |        |                                                   |
  |        |               cloud-controller-manager           |
  |        |               (solo su cloud managed)            |
  +--------+---------------------------------------------------+
           |  HTTPS (6443)
  WORKER NODES
  +------------------------------------------------------------+
  |  kubelet              kube-proxy         Container Runtime |
  |  +-----------+        +----------+       +-----------+    |
  |  | Pod lifecycle|     | iptables/|       | containerd|    |
  |  | Container   |      | ipvs     |       | CRI-O     |    |
  |  | probes      |      | Service  |       |           |    |
  |  | Resource    |      | routing  |       | runc      |    |
  |  | accounting  |      +----------+       +-----------+    |
  |  +-----------+                                            |
  +------------------------------------------------------------+
```

---

## kube-apiserver — Il Gateway del Cluster

L'**API server** è l'unico componente che parla direttamente con etcd. Tutti gli altri componenti comunicano tramite l'API server.

```
Request Lifecycle — kubectl apply -f deployment.yaml

  kubectl
    |
    v
  1. AUTHENTICATION — Chi sei?
     Meccanismi: X.509 client cert, Bearer token (SA), OIDC (OpenID Connect), webhook
     ServiceAccount token: JWT firmato da K8s, validato dall'API server
     Kubernetes 1.24+: tokens proiettati (bound SA tokens, scadenza configurabile)

    |
    v
  2. AUTHORIZATION — Cosa puoi fare?
     RBAC (Role-Based Access Control): verb (get/list/create/update/patch/delete/watch) su resource in namespace
     Controllato da: kube-apiserver
     Oggetti: Role/ClusterRole + RoleBinding/ClusterRoleBinding

    |
    v
  3. ADMISSION CONTROLLERS — È valido?
     Mutating Admission Webhooks (prima): modificano l'oggetto
       - DefaultStorageClass (aggiunge storageClass di default)
       - MutatingAdmissionWebhook (custom webhooks)
       - NamespaceLifecycle, LimitRanger
     Validating Admission Webhooks (dopo): validano (non modificano)
       - ValidatingAdmissionWebhook (OPA Gatekeeper, Kyverno)
       - ResourceQuota, PodSecurity

    |
    v
  4. OBJECT SCHEMA VALIDATION — È ben formato?
     Validation tramite OpenAPI schema per ogni GVK (Group/Version/Kind)

    |
    v
  5. PERSIST TO etcd
     Oggetto serializzato (protobuf) scritto in etcd

    |
    v
  6. RESPONSE all'utente

  (In parallelo: controllers e scheduler watchano le modifiche via Watch API)
```

**API Groups e Versioning:**

```bash
# K8s organizza le API in gruppi
kubectl api-resources --verbs=list -o wide | head -20
# NAME              SHORTNAMES  APIVERSION            NAMESPACED  KIND
# pods              po          v1                    true        Pod
# deployments       deploy      apps/v1               true        Deployment
# statefulsets      sts         apps/v1               true        StatefulSet
# ingresses         ing         networking.k8s.io/v1  true        Ingress
# certificates      cert        cert-manager.io/v1    true        Certificate

# GVK: Group/Version/Kind
# Group: "" (core) | apps | batch | networking.k8s.io | cert-manager.io
# Version: v1 | v1beta1 | v1alpha1
# Kind: Pod | Deployment | Ingress

# Esplora API disponibili
kubectl api-versions
kubectl explain pod.spec.containers.securityContext --recursive
kubectl explain deployment.spec.template.spec --recursive | head -50
```

---

## etcd — Database di Stato del Cluster

**etcd** è il database key-value distribuito che memorizza tutto lo stato del cluster Kubernetes. Usa il consenso **Raft** — un algoritmo di consenso distribuito che garantisce che tutte le scritture vengano applicate nello stesso ordine su tutti i nodi del cluster, anche in presenza di fallimenti.

```
etcd Raft Cluster (3 nodi)

  etcd-1 (leader)    etcd-2 (follower)   etcd-3 (follower)
  +-------------+    +-------------+     +-------------+
  | Raft Log    |    | Raft Log    |     | Raft Log    |
  | Committed   |<-->| Replicated  |<--> | Replicated  |
  | State       |    |             |     |             |
  +------+------+    +-------------+     +-------------+
         |
   Linearizable reads/writes
   (tutti i write passano per il leader)

  Quorum (numero minimo di nodi che devono concordare per validare un'operazione):
  majority = floor(N/2) + 1
  3 nodi → quorum = 2 → tollera 1 failure
  5 nodi → quorum = 3 → tollera 2 failure

  Raccomandazione: 3 nodi per prod, 5 nodi per alta disponibilità critica
                  mai 2, mai 4 (solo peggiorano il quorum)
```

**Struttura dei dati in etcd:**

```bash
# Leggi dati etcd direttamente (richiede accesso al cluster)
ETCDCTL_API=3 etcdctl \
    --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key \
    get /registry/pods/default/my-pod -w json | jq

# Tutti i pods in etcd
etcdctl get /registry/pods/ --prefix --keys-only

# Struttura key:
# /registry/<resource>/<namespace>/<name>
# /registry/pods/default/nginx-7848d4b86f-xyz
# /registry/deployments/production/api-server
# /registry/secrets/kube-system/bootstrap-token-xxx

# Backup etcd (CRITICO in produzione)
etcdctl snapshot save /backup/etcd-snapshot-$(date +%Y%m%d).db

# Restore (cluster down)
etcdctl snapshot restore /backup/etcd-snapshot.db \
    --name etcd-1 \
    --initial-cluster etcd-1=https://10.0.0.1:2380 \
    --initial-cluster-token etcd-cluster-1 \
    --initial-advertise-peer-urls https://10.0.0.1:2380 \
    --data-dir /var/lib/etcd-restore

# Encrypt secrets in etcd (best practice)
# /etc/kubernetes/encryption-config.yaml:
# resources:
#   - resources: ["secrets"]
#     providers:
#       - aescbc:
#           keys: [{name: key1, secret: <base64-32-bytes>}]
#       - identity: {}
```

---

## kube-scheduler — Decisione di Placement

Lo **scheduler** decide su quale nodo deve girare ogni Pod non ancora assegnato (`.spec.nodeName` vuoto).

```
Scheduling Pipeline — Fasi

  Pod senza nodeName
       |
       v
  1. FILTERING (predicates)
     Elimina nodi che NON soddisfano i requisiti:
     - NodeUnschedulable (cordon — nodo marcato come non schedulabile, nuovi Pod non vengono assegnati ma quelli esistenti restano)
     - ResourcesFit (requests CPU/memory <= node allocatable)
     - VolumeBinding (PVC disponibile sul nodo)
     - NodeAffinity (nodeSelector, affinity obbligatoria)
     - TaintToleration (il pod deve tollerare i taints del nodo)
     - PodTopologySpread (topologySpreadConstraints)
     - PodAffinity/AntiAffinity (regole hard)
     Risultato: lista di nodi feasible

       |
       v
  2. SCORING (priorities)
     Assegna un punteggio 0-100 a ogni nodo feasible:
     - NodeResourcesBalancedAllocation: prefer nodi con risorse bilanciate
     - LeastAllocated: prefer nodi con meno risorse allocate
     - NodeAffinity: punteggio per preferred affinity
     - PodAffinity: punteggio per preferred pod affinity
     - ImageLocality: prefer nodi che hanno già l'immagine
     - TaintToleration: penalizza tollerazioni preferite non soddisfatte
     Risultato: nodo con punteggio più alto

       |
       v
  3. BINDING
     scheduler scrive .spec.nodeName nel Pod → API server → etcd
     kubelet del nodo target vede il Pod assegnato e lo avvia
```

**Configurazione Scheduler:**

```yaml
# Scheduler Profile — Policy personalizzate
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
  - schedulerName: default-scheduler
    plugins:
      score:
        disabled:
          - name: NodeResourcesBalancedAllocation
        enabled:
          - name: NodeResourcesFit
            weight: 2
      filter:
        disabled: []
    pluginConfig:
      - name: NodeResourcesFit
        args:
          scoringStrategy:
            type: MostAllocated  # pack tight invece di spread
            resources:
              - name: cpu
                weight: 1
              - name: memory
                weight: 1
```

---

## kube-controller-manager — I Reconciliation Loop

Il **controller manager** esegue decine di controller in un singolo processo. Ogni controller implementa un **reconciliation loop**: confronta lo stato desiderato (spec) con lo stato attuale (status) e applica azioni correttive.

```
Reconciliation Loop Pattern

  DESIRED STATE (etcd/spec)          ACTUAL STATE (osservato)
       |                                    |
       v                                    v
  +-------------------------------------------+
  |           CONTROLLER LOOP                  |
  |                                             |
  |  current = observe_actual_state()           |
  |  desired = read_desired_state()             |
  |                                             |
  |  if current != desired:                     |
  |      actions = diff(current, desired)       |
  |      apply(actions)                         |
  |                                             |
  |  → Riavvia al prossimo evento (Watch)       |
  +-------------------------------------------+

  Esempi:
  Deployment Controller:
    desired: 3 replicas nginx:1.25
    actual: 2 running, 1 failed
    action: create new Pod con nginx:1.25

  Node Controller:
    desired: nodo online e sano
    actual: nodo non risponde da 5 minuti
    action: taint node + evict pods
```

**Meccanismo Watch — Efficienza O(1) per evento:**

```
Watch API — Come i Controller sono notificati

  etcd → API server → Controller (Watch stream)

  1. Controller: GET /api/v1/pods?watch=true&resourceVersion=12345
  2. API server: connessione HTTP long-lived aperta
  3. Ogni modifica in etcd → API server invia un event:
     {"type": "MODIFIED", "object": {...pod...}}
  4. Controller riceve l'evento e triggera la reconciliation

  IMPORTANTE: il controller non fa polling!
  Watch è una connessione streaming su HTTP/2.
  Resource Version: ogni oggetto ha un RV incrementale.
  Il controller tiene il proprio RV locale.
  Se si disconnette: riconnette con l'ultimo RV noto.

  Informer Pattern (client-go):
  - SharedIndexInformer: cache locale degli oggetti + event handlers
  - Lister: legge dalla cache locale (O(1), no API server call)
  - WorkQueue: code di reconciliation con rate-limiting
```

---

## kubelet — L'Agente del Nodo

Il **kubelet** è l'agente che gira su ogni nodo worker. È responsabile del ciclo di vita di tutti i Pod assegnati al nodo.

```
kubelet — Responsabilità

  API Server (Watch)
       |
       | Nuovo Pod assegnato al nodo
       v
  kubelet
    |
    |── 1. Valida Pod spec (sicurezza, resources, volumes)
    |── 2. Prepara volumi (monta PVC, configmap, secret)
    |── 3. Configura network namespace (via CNI plugin)
    |── 4. Crea containers (via CRI: containerd / CRI-O)
    |── 5. Avvia containers secondo l'ordine (init → sidecar → main)
    |── 6. Esegue probes:
    |       startupProbe    → aspetta che l'app si avvii (blocca liveness)
    |       livenessProbe   → uccide e ricrea se fallisce
    |       readinessProbe  → rimuove da endpoint se fallisce
    |── 7. Aggiorna Pod status → API server
    |── 8. Log handling (container stdout/stderr → /var/log/pods/)
    └── 9. Resource accounting (cgroups stats → Metrics API)

  Comunicazione con CRI (containerd):
  gRPC su /run/containerd/containerd.sock
  Protocollo: RuntimeService + ImageService (CRI API)
```

```bash
# Stato nodo e pod dal punto di vista del kubelet
systemctl status kubelet
journalctl -u kubelet -f                    # log kubelet in tempo reale
journalctl -u kubelet --since "10m ago" | grep -i error

# Verifica cosa il kubelet vede
kubectl get pods --field-selector spec.nodeName=worker-1

# Kubelet API (porta 10250) — vari endpoint
# Requires cert: --kubelet-certificate-authority e --kubelet-client-*
curl --cacert ca.crt --cert kubelet.crt --key kubelet.key \
    https://worker-1:10250/pods | jq '.items[].metadata.name'

# Configmap per configurazione kubelet
kubectl get configmap kubelet-config -n kube-system -o yaml
```

---

## kube-proxy — Service Routing sul Nodo

**kube-proxy** implementa la Virtual IP (ClusterIP) dei Service scrivendo regole iptables/ipvs su ogni nodo.

```
kube-proxy — Modalità iptables

  Service: ClusterIP = 10.96.0.1:80
  Backend Pods: [10.244.1.5:8080, 10.244.2.7:8080, 10.244.3.2:8080]

  iptables rules generate da kube-proxy:

  PREROUTING/OUTPUT:
  -A KUBE-SERVICES -d 10.96.0.1/32 -p tcp --dport 80 -j KUBE-SVC-XXXXX

  KUBE-SVC-XXXXX (load balancing con probabilità):
  -A KUBE-SVC-XXXXX -m statistic --mode random --probability 0.33 -j KUBE-SEP-A
  -A KUBE-SVC-XXXXX -m statistic --mode random --probability 0.50 -j KUBE-SEP-B
  -A KUBE-SVC-XXXXX -j KUBE-SEP-C

  KUBE-SEP-A (DNAT verso il pod):
  -A KUBE-SEP-A -p tcp -j DNAT --to-destination 10.244.1.5:8080

  Problema iptables: O(n) per ogni nuova connessione se ci sono molti Service
  → Performance degradata con 10.000+ Service

kube-proxy — Modalità IPVS (raccomandato per cluster grandi):
  IPVS (IP Virtual Server) opera nel kernel con hash table O(1):
  ipvsadm -Ln:
  TCP  10.96.0.1:80 rr         ← round-robin
    -> 10.244.1.5:8080         weight 1
    -> 10.244.2.7:8080         weight 1
    -> 10.244.3.2:8080         weight 1
```

```bash
# Verifica modalità kube-proxy
kubectl get configmap kube-proxy -n kube-system -o yaml | grep mode

# Cambia a IPVS mode
kubectl edit configmap kube-proxy -n kube-system
# mode: "ipvs"
# ipvs:
#   scheduler: "rr"          # round-robin | wrr | lc | wlc | sh

# Verifica regole IPVS
ipvsadm -Ln | head -30

# Debug Service routing
iptables -t nat -L KUBE-SERVICES -n | grep <cluster-ip>
```

---

## Alta Disponibilità del Control Plane

```
HA Control Plane — 3+ Master Node

  Load Balancer (HAProxy / NLB)
  kube-apiserver:6443
       |
       +-----+-----+-----+
       |           |     |
  master-1    master-2   master-3
  apiserver   apiserver  apiserver
  scheduler   scheduler  scheduler  ← Leader Election (Lease)
  ctrl-mgr    ctrl-mgr   ctrl-mgr   ← Leader Election (Lease)
       |           |     |
       +-----+-----+-----+
                  |
             etcd cluster
          (3 nodi separati o
           colocated con master)

  Leader Election (scheduler e controller-manager):
  Solo UN'istanza è attiva, le altre sono in standby.
  Meccanismo: Lease object in kube-system namespace.
  Se il leader non rinnova il Lease → failover automatico.

  kubectl get lease -n kube-system
  # NAME                       HOLDER                    AGE
  # kube-controller-manager    master-1_...             7d
  # kube-scheduler             master-1_...             7d
```

---

## Troubleshooting

### Scenario 1 — API server non raggiungibile

**Sintomo:** `kubectl` restituisce `Unable to connect to the server` o `connection refused` sulla porta 6443.

**Causa:** Il processo `kube-apiserver` è crashato, il certificato è scaduto, o il load balancer non instrada correttamente verso i master.

**Soluzione:**

```bash
# Verifica stato del pod statico apiserver (kubeadm)
sudo crictl ps | grep kube-apiserver
sudo crictl logs <container-id>

# Controlla i log del kubelet che lancia i pod statici
journalctl -u kubelet -n 100 | grep apiserver

# Verifica validità certificati (scadenza)
sudo openssl x509 -in /etc/kubernetes/pki/apiserver.crt -noout -dates
# Rinnovo certificati con kubeadm
sudo kubeadm certs check-expiration
sudo kubeadm certs renew all

# Se HA: verifica health di tutti gli endpoint
for ip in 10.0.0.1 10.0.0.2 10.0.0.3; do
  curl -sk https://$ip:6443/healthz && echo " $ip OK" || echo " $ip FAILED"
done
```

---

### Scenario 2 — Pod bloccato in Pending: nessun nodo idoneo

**Sintomo:** `kubectl get pods` mostra il Pod in stato `Pending` da più di qualche secondo. `kubectl describe pod <name>` riporta eventi come `0/3 nodes are available`.

**Causa:** Lo scheduler non trova nodi che superino la fase di filtering: risorse insufficienti, taints non tollerati, node affinity non soddisfatta, o PVC non legabile.

**Soluzione:**

```bash
# Leggi i motivi di Pending
kubectl describe pod <pod-name> -n <namespace> | grep -A 20 Events

# Verifica risorse disponibili sui nodi
kubectl describe nodes | grep -A 5 "Allocated resources"
kubectl top nodes

# Controlla taints presenti
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints

# Verifica se il PVC è Bound
kubectl get pvc -n <namespace>

# Simula scheduling senza eseguire (dry-run)
kubectl debug node/<node-name> --image=busybox -- sleep 1
```

---

### Scenario 3 — etcd degradato: cluster in quorum perso

**Sintomo:** Operazioni `kubectl` restituiscono `etcdserver: request timed out` o `context deadline exceeded`. Il cluster smette di accettare scritture.

**Causa:** Uno o più nodi etcd sono down e il quorum non è più raggiunto (es. 2 nodi su 3 sono offline).

**Soluzione:**

```bash
# Verifica health di tutti i membri etcd
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health --cluster

# Lista dei membri e loro stato
etcdctl member list -w table

# Se un nodo è irrecuperabile: rimuovilo e riaggiungi
etcdctl member remove <member-id>
etcdctl member add etcd-new --peer-urls=https://10.0.0.4:2380

# Restore da snapshot (caso estremo — cluster completamente down)
etcdctl snapshot restore /backup/etcd-snapshot.db \
  --name etcd-1 \
  --initial-cluster "etcd-1=https://10.0.0.1:2380" \
  --initial-cluster-token etcd-cluster-1 \
  --initial-advertise-peer-urls https://10.0.0.1:2380 \
  --data-dir /var/lib/etcd-new
```

---

### Scenario 4 — Pods evicted / nodo NotReady

**Sintomo:** Nodo passa a stato `NotReady`, i Pod vengono evicted o riassegnati. `kubectl describe node <name>` mostra condizioni come `MemoryPressure`, `DiskPressure`, o `KubeletNotReady`.

**Causa:** Il kubelet non invia heartbeat all'API server entro `node-monitor-grace-period` (default 40s). Cause tipiche: pressione di risorse, problema di rete, kubelet crashato.

**Soluzione:**

```bash
# Stato dettagliato del nodo
kubectl describe node <node-name> | grep -A 10 Conditions

# Accedi al nodo e verifica kubelet
ssh <node-ip>
systemctl status kubelet
journalctl -u kubelet --since "15m ago" | grep -E "error|Error|failed"

# Verifica pressione risorse
df -h /var/lib/kubelet   # DiskPressure
free -h                  # MemoryPressure

# Pulisci immagini e container non usati
crictl rmi --prune
crictl rm $(crictl ps -a -q --state Exited)

# Riavvia kubelet se necessario
systemctl restart kubelet

# Dal control plane: forza drain per manutenzione
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
kubectl uncordon <node-name>   # quando il nodo è pronto
```

---

## Riferimenti

- [Kubernetes Components](https://kubernetes.io/docs/concepts/overview/components/)
- [etcd FAQ](https://etcd.io/docs/v3.5/faq/)
- [Kubernetes Scheduler](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
- [kubelet](https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/)
- [kube-proxy](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-proxy/)
- [Controller Manager](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-controller-manager/)
