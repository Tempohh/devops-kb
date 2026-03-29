---
title: "Troubleshooting Kubernetes"
slug: troubleshooting
category: containers
tags: [kubernetes, troubleshooting, debug, kubectl, ephemeral-containers, events, logs]
search_keywords: [kubernetes troubleshooting, kubectl debug ephemeral container, kubernetes pod crashloopbackoff, kubernetes imagepullbackoff, kubectl describe pod, kubernetes node pressure, kubernetes OOMKilled, kubernetes pending pod, kubectl exec debug, kubernetes events, kubectl top, kubernetes node not ready]
parent: containers/kubernetes/_index
related: [containers/kubernetes/workloads, containers/kubernetes/scheduling-avanzato, containers/kubernetes/architettura]
official_docs: https://kubernetes.io/docs/tasks/debug/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Troubleshooting Kubernetes

## Approccio Sistematico

```
Troubleshooting Workflow

  1. Identifica il sintomo
     kubectl get pods -A | grep -v Running    # pod non-running
     kubectl get events -A --sort-by='.lastTimestamp' | tail -30

  2. Zoom sul pod
     kubectl describe pod <name> -n <ns>
     → Events (in fondo) sono la fonte primaria di info

  3. Log del container
     kubectl logs <pod> -n <ns>
     kubectl logs <pod> -n <ns> --previous    # log del container crashato

  4. Exec/Debug
     kubectl exec -it <pod> -n <ns> -- /bin/sh
     kubectl debug <pod> -it --image=nicolaka/netshoot

  5. Node level
     kubectl describe node <node>
     kubectl get events --field-selector involvedObject.name=<node>
```

---

## Diagnosi degli State del Pod

```
Pod Status → Causa Probabile

  Pending
  ├── Insufficient CPU/Memory        → kubectl describe pod: "Insufficient cpu"
  ├── No nodes match nodeSelector    → kubectl describe pod: "0/3 nodes available"
  ├── PVC non bound                  → kubectl get pvc -n <ns>
  ├── Image pull in corso            → normale se nuova immagine
  └── Scheduling bloccato (taint)   → kubectl describe pod: "taints that pod doesn't tolerate"

  ImagePullBackOff / ErrImagePull
  ├── Tag non esiste                 → verifica tag nel registry
  ├── Registry privato, no secret   → kubectl get secret; verificare imagePullSecrets
  ├── Registry irraggiungibile      → verifica connectivity dal nodo
  └── Rate limiting                 → Docker Hub ha rate limit per IP non autenticato

  CrashLoopBackOff
  ├── Applicazione crasha all'avvio  → kubectl logs --previous
  ├── Readiness probe fallisce       → kubectl describe pod → Liveness probe failed
  ├── OOM kill                       → kubectl describe pod: "OOMKilled"
  └── Mancano variabili d'ambiente  → verifica env e secret referenziati

  OOMKilled
  ├── Container supera memory limit → aumenta limit o ottimizza la app
  └── Memory leak                   → profiling applicativo

  Error / RunContainerError
  ├── Volume mount fallisce         → verifica PVC, permessi, CSI driver
  ├── securityContext conflitto     → runAsUser non esiste nell'immagine
  └── initContainer fallisce        → kubectl logs <pod> -c <init-container>

  Evicted
  ├── Node memory pressure          → kubectl describe node → Conditions: MemoryPressure
  ├── Node disk pressure            → DiskPressure
  └── PriorityClass bassa           → evicted per far posto a pod con priorità alta
```

---

## kubectl — Comandi Essenziali per Debug

```bash
# ── Overview rapida del cluster ────────────────────────────
kubectl get nodes -o wide                          # stato nodi
kubectl top nodes                                  # CPU/mem usage nodi
kubectl top pods -A --sort-by=memory | head -20   # pod per consumo mem

# ── Pod status in dettaglio ────────────────────────────────
kubectl get pods -A -o wide | grep -v Running | grep -v Completed
kubectl describe pod <name> -n <ns>                # tutto: events, conditions, volumes

# Informazioni su ogni container del pod
kubectl get pod <name> -n <ns> -o json | jq '
    .status.containerStatuses[] |
    {
        name: .name,
        ready: .ready,
        restartCount: .restartCount,
        state: .state,
        lastState: .lastState
    }'

# ── Log avanzati ───────────────────────────────────────────
kubectl logs <pod> -n <ns>                         # log correnti
kubectl logs <pod> -n <ns> --previous              # log container crashato
kubectl logs <pod> -n <ns> -c <container>          # container specifico
kubectl logs <pod> -n <ns> --all-containers        # tutti i container
kubectl logs <pod> -n <ns> --since=1h              # ultime 1h
kubectl logs <pod> -n <ns> --since-time=2026-02-25T10:00:00Z
kubectl logs -l app=api -n <ns> --prefix           # log da tutti i pod con label

# ── Events ────────────────────────────────────────────────
kubectl get events -n <ns> --sort-by='.lastTimestamp'
kubectl get events -n <ns> --field-selector reason=BackOff
kubectl get events -n <ns> --field-selector involvedObject.name=<pod>

# ── Exec nel container ────────────────────────────────────
kubectl exec -it <pod> -n <ns> -- /bin/sh
kubectl exec -it <pod> -n <ns> -c <container> -- bash
kubectl exec <pod> -n <ns> -- env | grep DB_      # variabili d'ambiente

# ── Port-forward per debug ─────────────────────────────────
kubectl port-forward pod/<pod> 8080:8080 -n <ns>
kubectl port-forward service/<svc> 8080:80 -n <ns>
kubectl port-forward deployment/<deploy> 8080:8080 -n <ns>

# ── Resource usage ────────────────────────────────────────
kubectl top pod <name> -n <ns> --containers        # per container
kubectl resource-capacity --pods                   # plugin krew
```

---

## Ephemeral Debug Containers

I **debug container** (Kubernetes 1.23+) iniettano un container temporaneo in un pod esistente, anche se il pod è `read_only` o usa `distroless`.

```bash
# Debug un pod con distroless (nessuna shell)
kubectl debug <pod> -n <ns> \
    -it \
    --image=nicolaka/netshoot \   # immagine ricca di tool di rete
    --target=<main-container>    # condivide il process namespace con il container target

# Il debug container può vedere:
# - Filesystem del container target (via /proc/<pid>/root/)
# - Process list del container (se --target è specificato)
# - Network namespace condiviso (stessa interfaccia di rete)

# Dopo il debug, il container ephemeral rimane (ma è terminato)
kubectl describe pod <pod> | grep -A5 "Ephemeral Containers"

# Debug un nodo (crea un pod privilegiato sul nodo)
kubectl debug node/worker-1 \
    -it \
    --image=ubuntu:22.04
# → mount /host per accedere al filesystem del nodo
# → usa crictl, journalctl, ps aux per diagnostica

# Debug con copia del pod (modifica il comando)
kubectl debug <pod> -n <ns> \
    -it \
    --copy-to=debug-pod \
    --container=<container> \
    --image=ubuntu:22.04 \
    -- /bin/bash
# Crea un nuovo pod copia (non modifica il pod originale)
# Utile per debug senza disturbare il pod in produzione
```

---

## Troubleshooting Networking

```bash
# Test DNS interno
kubectl run dns-test --image=nicolaka/netshoot --rm -it -- \
    nslookup kubernetes.default.svc.cluster.local

# Test connettività service
kubectl run curl-test --image=nicolaka/netshoot --rm -it -- \
    curl -v http://api-service.production.svc.cluster.local:8080/health

# Ispeziona endpoints di un service
kubectl get endpoints <service> -n <ns>
kubectl describe endpoints <service> -n <ns>

# Problema: service non risponde
# Verifica che i pod siano nel endpoint:
kubectl get ep <service> -n <ns>
# NAME   ENDPOINTS           AGE
# api    <none>              5d     ← PROBLEMA: nessun endpoint!
# Causa possibile: labels del pod non matchano il selector del service
kubectl get svc <service> -n <ns> -o yaml | grep selector
kubectl get pods -n <ns> -l <selector-labels>

# Debug NetworkPolicy
# Tool: Cilium hubble (se usi Cilium come CNI)
hubble observe --pod <pod> --follow
# Oppure: policy-tester offline
kubectl get netpol -n <ns> -o yaml

# Traccia connessione end-to-end
kubectl run tracer --image=nicolaka/netshoot --rm -it -- \
    traceroute <destination-ip>
```

---

## Troubleshooting Storage

```bash
# PVC non si lega a un PV
kubectl describe pvc <pvc> -n <ns>
# Events: No matching PersistentVolume found
# Cause: capacity, accessMode, storageClass non compatibili con nessun PV

# CSI driver non risponde
kubectl get pods -n kube-system | grep csi
kubectl logs -n kube-system <csi-controller-pod> -c csi-provisioner

# Volume mount fallisce nel pod
kubectl describe pod <pod> | grep -A5 "Warning"
# Warning FailedMount: MountVolume.SetUp failed for volume "data":
# mount failed: exit status 32  → verifica permessi, filesystem, quota

# Verifica che il volume sia montato
kubectl exec <pod> -- df -h /data
kubectl exec <pod> -- ls -la /data

# Performance storage
kubectl exec <pod> -- \
    dd if=/dev/zero of=/data/test bs=1M count=1000 conv=fdatasync
```

---

## Troubleshooting Nodi

```bash
# Nodo NotReady
kubectl describe node <node>
# Conditions:
#   MemoryPressure   True    → kubelet ha meno memoria di threshold
#   DiskPressure     True    → disco quasi pieno
#   PIDPressure      True    → troppi processi
#   Ready            False   → kubelet non risponde all'API server

# Sul nodo stesso:
journalctl -u kubelet --since "30m ago" | grep -i error
systemctl status kubelet
crictl ps                    # lista container live (come docker ps ma con CRI)
crictl logs <container-id>

# Disk pressure: trova cosa occupa spazio
du -sh /var/lib/docker/*     # se usa docker
du -sh /var/lib/containerd/* # se usa containerd
# Cleanup immagini non usate
crictl rmi --prune

# Memory pressure
free -h
cat /proc/meminfo | grep -E "MemAvailable|Cached"
ps aux --sort=-%mem | head -20

# CPU throttling
cat /sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/*/cpu.stat | grep throttled
```

---

## Comandi kubectl Avanzati

```bash
# JSON Path — estrai campi specifici
kubectl get pods -A -o jsonpath='{range .items[?(@.status.phase!="Running")]}{.metadata.namespace}/{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'

# Custom columns
kubectl get pods -n production \
    -o custom-columns=\
NAME:.metadata.name,\
NODE:.spec.nodeName,\
STATUS:.status.phase,\
RESTARTS:.status.containerStatuses[0].restartCount,\
CPU-REQ:.spec.containers[0].resources.requests.cpu,\
MEM-REQ:.spec.containers[0].resources.requests.memory

# Trova pod con OOMKilled recente
kubectl get pods -A -o json | jq -r '
    .items[] |
    .metadata.namespace as $ns |
    .metadata.name as $pod |
    .status.containerStatuses[]? |
    select(.lastState.terminated.reason == "OOMKilled") |
    [$ns, $pod, .name, (.lastState.terminated.finishedAt // "unknown")] |
    @tsv'

# Verifica tutti i resource requests del cluster
kubectl get pods -A -o json | jq -r '
    .items[].spec.containers[] |
    [.name, (.resources.requests.cpu // "none"), (.resources.requests.memory // "none")] |
    @tsv' | sort | uniq -c | sort -rn

# Lista tutti gli image usati nel cluster
kubectl get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' | sort | uniq

# Watch eventi in tempo reale
kubectl get events -A -w --sort-by='.lastTimestamp'

# Drain pianificato con log
kubectl drain <node> \
    --ignore-daemonsets \
    --delete-emptydir-data \
    --grace-period=60 \
    --timeout=300s \
    --dry-run=client    # simula prima di eseguire
```

---

## krew Plugins Utili

```bash
# Installa krew (plugin manager)
# https://krew.sigs.k8s.io/docs/user-guide/setup/install/

# Plugin essenziali per troubleshooting
kubectl krew install \
    ctx \        # cambia context rapidamente (kubectx)
    ns \         # cambia namespace (kubens)
    top \        # enhanced top
    neat \       # rimuove campi managed fields dall'output yaml
    images \     # lista immagini per pod
    resource-capacity \  # mostra capacità cluster con usage
    tree \       # mostra gerarchia degli oggetti (owner references)
    stern \      # multi-pod log tailing
    konfig \     # merge kubeconfig files
    deprecations  # trova API deprecate nel cluster

# Uso
kubectl ctx                          # lista context
kubectl ctx production               # cambia a context production
kubectl ns production                # cambia namespace default
kubectl tree deployment/api -n prod  # mostra ReplicaSet → Pod hierarchy
stern "api-.*" -n production         # log da tutti i pod api-*
```

---

## Troubleshooting

### Scenario 1 — Pod in CrashLoopBackOff dopo deploy

**Sintomo:** Il pod entra in CrashLoopBackOff subito dopo il deploy; `kubectl get pods` mostra RESTARTS in aumento.

**Causa:** L'applicazione crasha all'avvio per configurazione errata (env mancante, secret non montato, dipendenza non raggiungibile) oppure la liveness probe è troppo aggressiva.

**Soluzione:** Leggere i log del container precedente e la descrizione del pod per individuare la causa.

```bash
# Log dell'ultima esecuzione crashata
kubectl logs <pod> -n <ns> --previous

# Dettaglio eventi e probe
kubectl describe pod <pod> -n <ns>
# Cercare: "Liveness probe failed", "OOMKilled", "Error from container"

# Verifica variabili d'ambiente effettivamente iniettate
kubectl exec <pod> -n <ns> -- env | sort

# Se la liveness probe è troppo aggressiva, aumentare initialDelaySeconds
kubectl edit deployment <deploy> -n <ns>
# → spec.template.spec.containers[].livenessProbe.initialDelaySeconds: 60
```

---

### Scenario 2 — Service non raggiunge nessun Pod (Endpoints vuoti)

**Sintomo:** `curl` sul service restituisce "connection refused" o timeout; `kubectl get endpoints <svc>` mostra `<none>`.

**Causa:** Il `selector` del Service non corrisponde alle `labels` dei pod — spesso per un typo nel label o per una modifica al Deployment che non ha aggiornato il Service.

**Soluzione:** Confrontare il selector del Service con le label effettive dei pod.

```bash
# Mostra il selector del service
kubectl get svc <service> -n <ns> -o jsonpath='{.spec.selector}'

# Mostra le label dei pod che dovrebbero essere selezionati
kubectl get pods -n <ns> --show-labels

# Verifica endpoint live
kubectl get endpoints <service> -n <ns>

# Quick test: seleziona manualmente i pod con le label attese
kubectl get pods -n <ns> -l app=<value>,tier=<value>

# Fix: aggiorna il selector del service o le label del Deployment
kubectl label pod <pod> -n <ns> app=<correct-value> --overwrite
```

---

### Scenario 3 — Nodo in stato NotReady

**Sintomo:** `kubectl get nodes` mostra un nodo `NotReady`; i pod sul nodo risultano in `Unknown` o vengono evicted.

**Causa:** Il kubelet sul nodo ha smesso di comunicare con l'API server. Cause frequenti: kubelet crashato, disco pieno, pressione di memoria, problemi di rete al nodo.

**Soluzione:** Controllare lo stato del kubelet sul nodo e le Conditions riportate.

```bash
# Condizioni del nodo
kubectl describe node <node> | grep -A10 "Conditions:"

# Sul nodo via SSH
systemctl status kubelet
journalctl -u kubelet --since "30m ago" | grep -iE "error|fail|fatal"

# Verifica disco
df -h
du -sh /var/lib/containerd/*
crictl rmi --prune   # rimuovi immagini non usate

# Verifica memoria
free -h
ps aux --sort=-%mem | head -10

# Riavvio kubelet se il processo è crashed
systemctl restart kubelet
systemctl enable kubelet
```

---

### Scenario 4 — PVC bloccato in stato Pending

**Sintomo:** Il pod rimane `Pending` e `kubectl get pvc` mostra il PVC in stato `Pending` indefinitamente.

**Causa:** Nessun PersistentVolume disponibile corrisponde alle richieste del PVC (capacità, `accessModes`, `storageClassName` incompatibili) oppure il CSI driver non è funzionante.

**Soluzione:** Ispezionare gli eventi del PVC e verificare la compatibilità con i PV disponibili o il provisioner dinamico.

```bash
# Dettaglio eventi del PVC
kubectl describe pvc <pvc> -n <ns>
# Cercare: "no matching PersistentVolume", "waiting for first consumer"

# Lista PV disponibili e loro stato
kubectl get pv -o wide

# Confronta storageClass del PVC con quelle disponibili
kubectl get pvc <pvc> -n <ns> -o jsonpath='{.spec.storageClassName}'
kubectl get storageclass

# Verifica CSI driver (provisioner dinamico)
kubectl get pods -n kube-system | grep csi
kubectl logs -n kube-system <csi-controller-pod> -c csi-provisioner --tail=50

# Se volumeBindingMode=WaitForFirstConsumer: il PV viene creato solo quando il pod è schedulato
kubectl get storageclass <class> -o jsonpath='{.volumeBindingMode}'
```

---

## Riferimenti

- [Debugging Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/)
- [Ephemeral Containers](https://kubernetes.io/docs/concepts/workloads/pods/ephemeral-containers/)
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [Node Debugging](https://kubernetes.io/docs/tasks/debug/debug-cluster/kubectl-node-debug/)
- [krew plugins](https://krew.sigs.k8s.io/plugins/)
