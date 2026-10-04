---
title: "Sandboxing Avanzato"
slug: sandboxing-avanzato
category: containers
tags: [gvisor, kata-containers, firecracker, sandboxing, security, runtime-isolation]
search_keywords: [gVisor runsc, Kata Containers QEMU, Firecracker microVM, container sandboxing, gVisor kernel interception, Kata Containers nested virtualization, runsc KVM, gVisor ptrace mode, container isolation security, sandbox runtime kubernetes, trusted vs untrusted workloads]
parent: containers/container-runtime/_index
related: [containers/docker/sicurezza, containers/kubernetes/sicurezza, containers/container-runtime/_index]
official_docs: https://gvisor.dev/docs/
status: reviewed
difficulty: expert
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Sandboxing Avanzato

## Il Problema del Kernel Condiviso

I container standard condividono il kernel Linux dell'host. Una vulnerabilità del kernel (CVE nel syscall layer) può permettere il container escape.

```
Threat Model — Kernel Shared vs Sandboxed

  CONTAINER STANDARD:
  Container Process
       |
       | syscall (open, read, write, clone, ...)
       v
  Linux Kernel (HOST)    ← attacco diretto al kernel host possibile
  Hardware

  SANDBOXED (gVisor):
  Container Process
       |
       | syscall
       v
  gVisor Kernel (user-space) ← kernel alternativo intercetta le syscall
       |
       | pochi syscall filtrati
       v
  Linux Kernel (HOST)    ← superficie di attacco drasticamente ridotta
  Hardware

  SANDBOXED (Kata Containers):
  Container Process
       |
       | syscall
       v
  Kata Kernel (dentro VM leggera) ← kernel separato per ogni pod
       |
       | hypercall (hypervisor)
       v
  QEMU/Firecracker (hypervisor) ← layer di virtualizzazione
  Linux Kernel (HOST)
  Hardware
```

---

## gVisor — User-Space Kernel

**gVisor** (Google) è un kernel user-space scritto in Go che intercetta le syscall dei container prima che raggiungano il kernel host.

```
gVisor Architecture

  Container Process (PID N)
       |
  seccomp filter: TRAP (non DENY) → cattura le syscall
       |
       v
  Sentry (gVisor kernel) — processo user-space
  +------------------------------------------+
  |  Implementa POSIX syscall interface       |
  |  Subset delle syscall Linux (no io_uring, |
  |  bpf, perf_event_open)                    |
  |  Written in Go (memory-safe)              |
  |  Gestisce:                                |
  |  - Filesystem (via Gofer)                 |
  |  - Network (netstack Golang)              |
  |  - Process management                     |
  |  - Memory management                      |
  +------------------------------------------+
       |
       | solo syscall necessarie al Sentry
       v
  Linux Kernel (HOST) — ridotta superficie
```

**Platform di intercettazione** (come il Sentry cattura le syscall dell'app):

```
systrap (default dal 2023, non richiede KVM):
  - seccomp SECCOMP_RET_TRAP + signal handler: l'app notifica il Sentry
  - Funziona su qualsiasi Linux, anche in VM cloud senza nested virt
  - Overhead molto inferiore a ptrace: scelta consigliata nella maggior parte dei casi

KVM:
  - Il Sentry usa KVM per far girare l'app in un address space guest
  - Costo di syscall/context switch più basso su bare metal
  - Richiede /dev/kvm; su VM cloud con nested virt può risultare PIÙ lento di systrap

ptrace (legacy, deprecata):
  - Overhead alto; mantenuta solo per compatibilità, non usarla per nuovi deployment
```

!!! note "Perché un kernel user-space"
    Il Sentry è scritto in Go (memory-safe) e gestisce le syscall al posto del kernel host: un bug nell'implementazione di una syscall compromette il Sentry, non l'host. Il Sentry stesso gira con un filtro seccomp stretto, quindi verso l'host espone solo una piccola parte della superficie syscall.

```bash
# Installazione runsc (gVisor runtime)
curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] \
    https://storage.googleapis.com/gvisor/releases release main" > /etc/apt/sources.list.d/gvisor.list
apt-get update && apt-get install -y runsc

# Configura containerd per gVisor (/etc/containerd/config.toml)
# [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc]
#   runtime_type = "io.containerd.runsc.v1"
#   [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc.options]
#     TypeUrl = "io.containerd.runsc.v1.options"
#     ConfigPath = "/etc/containerd/runsc.toml"

# /etc/containerd/runsc.toml
# [runsc_config]
#   platform = "systrap"   # systrap (default) | kvm | ptrace (deprecata)
#   file-access = "shared" # per performance I/O (shared host filesystem)

# Verifica
runsc --version
# runsc version release-<data>   (le release sono datate, es. release-20260105.0)
```

**Performance gVisor:**

```
gVisor Performance Trade-offs

  Overhead iniziale:
  - ~50MB RAM aggiuntiva per il Sentry process per pod
  - Startup time: +100-500ms

  Overhead runtime:
  - Syscall-intensive workloads: 2-10x overhead
  - Compute-intensive (pochi syscall): ~5-15% overhead
  - Network (netstack): 10-30% throughput in meno

  NON adatto per:
  - Database (I/O intensivo)
  - Machine Learning (compute + syscall intensive)
  - Alta frequenza di fork/exec

  Adatto per:
  - Workloads untrusted (multi-tenant, customer code)
  - API server (moderate syscall rate)
  - Batch job da sorgenti esterne
  - Ambienti che richiedono compliance alta
```

---

## Kata Containers — VM-Based Containers

**Kata Containers** (OpenInfra Foundation) esegue ogni pod in una VM leggera (QEMU, Firecracker, Cloud Hypervisor). Combina la velocità dei container con l'isolamento delle VM.

```
Kata Containers Architecture

  Pod Kubernetes
  +------------------------------------------+
  |  Container A      Container B             |
  |  (shared kernel)  (shared kernel)         |
  |       |                |                  |
  |  Kata Agent (dentro VM) — gestisce i ctr  |
  +------------------------------------------+
       |
       | virtio (periferiche virtuali)
       | virtio-fs (filesystem condiviso)
       v
  QEMU / Firecracker / Cloud Hypervisor
  (hypervisor leggero)
       |
  Linux Kernel (HOST)

  Ogni POD ha il proprio:
  - Kernel Linux (lightweight, avvio < 1s)
  - Memory virtuale isolata
  - Rete virtuale (tap device)
  - Filesystem virtuale

  I container nello stesso pod condividono la VM
  (come nel modello standard K8s, ma la VM è l'unità di isolamento)
```

```bash
# Installazione Kata Containers
# 1. Installa Kata
# Su host: pacchetti della distro o release tarball (kata-static) da GitHub
# Su Kubernetes: kata-deploy (Helm chart: DaemonSet che installa il runtime e registra le RuntimeClass).
#   Il vecchio kata-operator è deprecato.
helm install kata-deploy oci://ghcr.io/kata-containers/kata-deploy-charts/kata-deploy \
  --namespace kube-system   # verificare chart/valori nella doc ufficiale

# 2. Verifica che nested virtualization sia disponibile
cat /proc/cpuinfo | grep -E "vmx|svm"   # vmx=Intel, svm=AMD
ls /dev/kvm    # deve esistere

# 3. Configura containerd per Kata
# [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-qemu]
#   runtime_type = "io.containerd.kata.v2"
#   pod_annotations = ["io.katacontainers.*"]
#   container_annotations = ["io.katacontainers.*"]
#   [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-qemu.options]
#     ConfigPath = "/opt/kata/share/defaults/kata-containers/configuration-qemu.toml"

# Verifica
kata-runtime check    # verifica i requisiti HW
kata-runtime kata-env # mostra la configurazione

# Test: run un container con Kata
docker run --runtime io.containerd.kata.v2 ubuntu:22.04 uname -r
# <versione kernel guest Kata>  ← diverso dal kernel host!
```

**Comparazione QEMU vs Firecracker per Kata:**

| | QEMU | Firecracker |
|---|---|---|
| **Startup** | ~800ms-2s | ~125ms |
| **Memory overhead** | ~150-200MB | ~5MB |
| **Compatibilità** | Massima (emula HW completo) | Limitata (no USB/PCI/GPU, no virtio-fs: serve block device, es. snapshotter devmapper) |
| **Features** | Tutto (GPU passthrough, PCI) | Minimalista |
| **Usato da** | Default Kata | AWS Lambda, Fargate (hypervisor diretto, non via Kata) |
| **Miglior uso** | Workloads che richiedono device | Serverless, funzioni brevi |

---

## Firecracker — MicroVM per Serverless

**Firecracker** (Amazon) è un hypervisor minimale progettato per funzioni serverless. Ogni function Lambda e ogni task Fargate gira in una Firecracker microVM.

```
Firecracker MicroVM

  Caratteristiche:
  - Boot di una microVM in ~125ms
  - ~5MB overhead di memoria per microVM
  - Device model minimale (no USB, no PCI passthrough, no BIOS: boot diretto del kernel)
  - Solo KVM (nessun emulazione software)
  - Scritto in Rust (memory-safe)
  - API REST per la gestione (no monitor QEMU)

  Dispositivi supportati:
  - Virtio net (rete)
  - Virtio block (storage)
  - Virtio vsock (comunicazione host-guest)
  - Serial console (per log)
  - Clock (rtc)

  Usato in produzione da:
  - AWS Lambda
  - AWS Fargate
  - Fly.io (isolamento tenant)
  - Sandbox per codice generato da agenti AI (es. E2B)
```

```bash
# Firecracker + containerd (via firecracker-containerd, progetto poco attivo)
# https://github.com/firecracker-microvm/firecracker-containerd
# In pratica si usa Kata + Firecracker (richiede snapshotter devmapper, no virtio-fs)

# Con Kata + Firecracker:
# /opt/kata/share/defaults/kata-containers/configuration-fc.toml
# [hypervisor.firecracker]
# path = "/usr/local/bin/firecracker"
# kernel = "/opt/kata/share/kata-containers/vmlinux-5.15.kata"
# initrd = "/opt/kata/share/kata-containers/kata-initrd.img"
```

---

## Quando Usare Cosa — Decision Matrix

```
RUNTIME SELECTION

  Workload | Risk | Caratteristiche    → Runtime
  ─────────────────────────────────────────────────────────────
  API servers aziendali (trusted)      → runc (default)
  Database (I/O intensive, trusted)    → runc + security hardening

  Customer code (untrusted, moderate)  → gVisor
  Batch job da sorgenti esterne        → gVisor
  Multi-tenant SaaS (moderate risk)    → gVisor

  Codice altamente untrusted           → Kata Containers (QEMU)
  Compliance rigorosa (PCI, HIPAA)     → Kata Containers
  AI/ML da vendor non trusted          → Kata Containers

  Serverless / funzioni corte          → Firecracker
  Edge computing, alta densità         → Firecracker

  Standard enterprise K8s cluster:
  → Mix: runc per workloads trusted, gVisor per untrusted,
         RuntimeClass per selezione per namespace/pod
```

In Kubernetes la `RuntimeClass` mappa un nome all'handler configurato in containerd; `scheduling.nodeSelector` limita ai nodi che hanno quel runtime.

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc          # nome del runtime in containerd
scheduling:
  nodeSelector:
    sandbox.gvisor/enabled: "true"
---
apiVersion: v1
kind: Pod
metadata:
  name: untrusted-job
spec:
  runtimeClassName: gvisor
  containers:
    - name: app
      image: busybox:1.37
      command: ["sleep", "3600"]
```

!!! tip "Servizi gestiti e confidential computing"
    GKE Sandbox è gVisor gestito. Kata è la base dei Confidential Containers (CNCF CoCo) per TEE hardware (AMD SEV-SNP, Intel TDX).

---

## Troubleshooting

### Scenario 1 — gVisor: container crasha per syscall non supportata

**Sintomo:** Il container si avvia ma crasha immediatamente con errori tipo `Function not implemented` o `invalid argument`.

**Causa:** Il workload usa syscall non implementate dal Sentry gVisor (implementa solo un sottoinsieme delle syscall Linux). Spesso: `io_uring`, `perf_event_open`, `bpf`.

**Soluzione:** Verificare quali syscall mancano, valutare se usare Kata invece di gVisor per quel workload.

```bash
# Abilitare strace-like logging in gVisor per identificare le syscall non supportate
# /etc/containerd/runsc.toml
# [runsc_config]
#   strace = true
#   strace-syscalls = ""   # "" = tutte

# Oppure avviare il container con debug logging
runsc --debug --debug-log=/tmp/gvisor-debug.log run <container-id>

# Cercare le syscall fallite nei log
grep -i "unimplemented\|not implemented\|ENOSYS" /tmp/gvisor-debug.log

# Tabelle ufficiali syscall supportate:
# https://gvisor.dev/docs/user_guide/compatibility/linux/amd64/
```

---

### Scenario 2 — Kata Containers: `kata-runtime check` fallisce con KVM non disponibile

**Sintomo:** `kata-runtime check` restituisce `ERROR: kernel module kvm requires root privileges` o `could not access /dev/kvm`.

**Causa:** Nested virtualization non abilitata sul nodo (comune su VM cloud), oppure il modulo KVM non è caricato. Kata richiede sempre KVM.

**Soluzione:** Abilitare nested virt sul cloud provider o sull'hypervisor host, oppure usare nodi bare metal. Se KVM non è disponibile, usare gVisor con platform systrap (non lo richiede).

```bash
# Verifica moduli KVM
lsmod | grep kvm
cat /proc/cpuinfo | grep -E "vmx|svm"

# Caricamento moduli (Intel / AMD)
modprobe kvm_intel   # Intel
modprobe kvm_amd     # AMD

# AWS: abilitare nested virt sulla istanza EC2
# L'istanza deve essere di tipo .metal o supportare nested virt

# Verifica completa dell'ambiente Kata
kata-runtime kata-env
kata-runtime check --verbose
```

---

### Scenario 3 — RuntimeClass non trovata o pod rimane in `Pending`

**Sintomo:** Il pod resta in `Pending` con evento `Failed to create pod sandbox: no runtime for "kata-qemu" is configured`.

**Causa:** La RuntimeClass è definita in Kubernetes ma il nodo non ha il runtime corrispondente configurato in containerd, oppure il nodo non ha il label corretto per il node selector.

**Soluzione:** Verificare la configurazione containerd su tutti i nodi target e aggiungere node selector alla RuntimeClass.

```bash
# Verifica che la RuntimeClass esista
kubectl get runtimeclass

# Descrivi la RuntimeClass per vedere il node selector
kubectl describe runtimeclass kata-qemu

# Verifica la configurazione containerd sul nodo
# Sul nodo:
cat /etc/containerd/config.toml | grep -A5 "kata"

# Riavvia containerd dopo modifiche
systemctl restart containerd

# Testa direttamente il runtime
ctr run --runtime io.containerd.kata.v2 --rm docker.io/library/busybox:latest test sh -c "uname -r"

# Evento del pod per il debug
kubectl describe pod <pod-name> | grep -A10 "Events:"
```

---

### Scenario 4 — Performance degradate con gVisor su I/O intensivo

**Sintomo:** Workload con I/O elevato (database, log processing) è 5-10x più lento con gVisor rispetto a runc.

**Causa:** Il filesystem Gofer in gVisor introduce overhead significativo per ogni operazione I/O. La modalità `shared` riduce l'overhead ma aumenta la superficie.

**Soluzione:** Ottimizzare la configurazione del file-access oppure escludere i workloads I/O-intensivi da gVisor usando RuntimeClass selettive.

```bash
# /etc/containerd/runsc.toml — opzioni per ridurre overhead I/O
# [runsc_config]
#   file-access = "shared"    # shared = meno safe ma più veloce (default: exclusive)
#   overlay2 = "root:self"    # overlay del rootfs (default); "none" lo disabilita
#   network = "host"          # network=host elimina il netstack overhead (richiede trust)

# Benchmark per confrontare runc vs gVisor
docker run --rm --runtime io.containerd.runc.v2 ubuntu dd if=/dev/zero of=/tmp/test bs=1M count=512 oflag=dsync
docker run --rm --runtime io.containerd.runsc.v1 ubuntu dd if=/dev/zero of=/tmp/test bs=1M count=512 oflag=dsync

# Usa RuntimeClass diversi per namespace differenti
kubectl label namespace untrusted-workloads sandbox=gvisor
# Poi usa un admission webhook o RuntimeClass nel workload spec
```

---

## Riferimenti

- [gVisor Documentation](https://gvisor.dev/docs/)
- [gVisor GitHub](https://github.com/google/gvisor)
- [Kata Containers](https://katacontainers.io/)
- [Firecracker](https://firecracker-microvm.github.io/)
- [Kubernetes RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/)
