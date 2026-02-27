---
title: "Sandboxing Avanzato"
slug: sandboxing-avanzato
category: containers
tags: [gvisor, kata-containers, firecracker, sandboxing, security, runtime-isolation]
search_keywords: [gVisor runsc, Kata Containers QEMU, Firecracker microVM, container sandboxing, gVisor kernel interception, Kata Containers nested virtualization, runsc KVM, gVisor ptrace mode, container isolation security, sandbox runtime kubernetes, trusted vs untrusted workloads]
parent: containers/container-runtime/_index
related: [containers/docker/sicurezza, containers/kubernetes/sicurezza, containers/container-runtime/_index]
official_docs: https://gvisor.dev/docs/
status: complete
difficulty: expert
last_updated: 2026-02-25
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
  |  ~ 200 syscall supportate (subset Linux)  |
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

**Due modalità di intercettazione:**

```
ptrace mode (default, non richiede KVM):
  - Sentry usa ptrace() per intercettare le syscall del container
  - Maggiore portabilità (funziona su qualsiasi Linux)
  - Performance peggiore (ptrace ha overhead significativo)
  - Utile per: ambienti senza virtualizzazione hardware (VM cloud annidate)

KVM mode (raccomandato per produzione):
  - Sentry gira come una VM leggera (usa KVM direttamente)
  - Migliore isolamento (hardware boundary)
  - Performance migliore rispetto a ptrace
  - Richiede: accesso a /dev/kvm (nested virt su cloud o bare metal)
```

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
#   platform = "kvm"       # kvm | ptrace | systrap
#   file-access = "shared" # per performance I/O (shared host filesystem)

# Verifica
runsc --version
# runsc version release-20240212.0
# spec: 1.0.2-dev
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

**Kata Containers** (OpenStack Foundation) esegue ogni pod in una VM leggera (QEMU, Firecracker, Cloud Hypervisor). Combina la velocità dei container con l'isolamento delle VM.

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
# 1. Install Kata packages
dnf install -y kata-containers
# oppure:
kubectl apply -f https://github.com/kata-containers/kata-containers/releases/latest/download/kata-operator.yaml

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
# 5.15.0-kata-containers  ← diverso dal kernel host!
```

**Comparazione QEMU vs Firecracker per Kata:**

| | QEMU | Firecracker |
|---|---|---|
| **Startup** | ~800ms-2s | ~125ms |
| **Memory overhead** | ~150-200MB | ~5MB |
| **Compatibilità** | Massima (emula HW completo) | Limitata (no USB, no serial) |
| **Features** | Tutto (GPU passthrough, PCI) | Minimalista |
| **Usato da** | Default Kata | AWS Lambda, Fargate |
| **Miglior uso** | Workloads che richiedono device | Serverless, funzioni brevi |

---

## Firecracker — MicroVM per Serverless

**Firecracker** (Amazon) è un hypervisor minimale progettato per funzioni serverless. Ogni function Lambda e ogni task Fargate gira in una Firecracker microVM.

```
Firecracker MicroVM

  Caratteristiche:
  - ~5ms per creare una microVM (record di velocità)
  - ~5MB overhead di memoria
  - No dispositivi legacy (no serial, no USB, no BIOS)
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
  - Cloudflare Workers (sperimentale)
```

```bash
# Firecracker + containerd (via firecracker-containerd)
# https://github.com/firecracker-microvm/firecracker-containerd

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

---

## Riferimenti

- [gVisor Documentation](https://gvisor.dev/docs/)
- [gVisor GitHub](https://github.com/google/gvisor)
- [Kata Containers](https://katacontainers.io/)
- [Firecracker](https://firecracker-microvm.github.io/)
- [Kubernetes RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/)
