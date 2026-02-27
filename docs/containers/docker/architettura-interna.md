---
title: "Architettura Interna Docker"
slug: architettura-interna
category: containers
tags: [docker, namespaces, cgroups, unionfs, overlay2, oci, containerd, runc, kernel]
search_keywords: [docker internals, linux namespaces containers, cgroups docker, union filesystem overlay2, OCI image spec, OCI runtime spec, docker daemon containerd, runc container, docker architecture deep, pid namespace network namespace]
parent: containers/docker/_index
related: [containers/container-runtime/_index, containers/docker/sicurezza]
official_docs: https://docs.docker.com/engine/
status: complete
difficulty: expert
last_updated: 2026-02-25
---

# Architettura Interna Docker

## Il Modello a Layer: Docker Engine

L'architettura Docker è diventata progressivamente più modulare. Capirla significa capire ogni componente nella catena dalla CLI al kernel.

```
Docker Architecture Stack

  docker CLI          docker-compose
       |                    |
       +--------+-----------+
                |
                v
  +--------------------------+
  |  Docker Daemon (dockerd)  |
  |  gRPC server             |
  |  Image management        |
  |  Volume management       |
  |  Network management      |
  +-----------+--------------+
              | gRPC (containerd API)
              v
  +--------------------------+
  |  containerd              |
  |  Image pull/push (OCI)   |
  |  Snapshot management     |
  |  Container lifecycle     |
  |  Task management         |
  +-----------+--------------+
              | exec shim
              v
  +--------------------------+
  |  containerd-shim-runc-v2  |
  |  (process per container) |
  |  Persiste dopo dockerd    |
  |  restart                 |
  +-----------+--------------+
              | OCI Runtime Spec
              v
  +--------------------------+
  |  runc                    |
  |  Chiama le syscall Linux  |
  |  Crea namespaces         |
  |  Configura cgroups       |
  |  Esegue il processo init |
  +---------------------------+
              |
              v
  Linux Kernel (namespaces + cgroups + seccomp)
```

**Perché questo layering?**

- `containerd` può essere usato direttamente (Kubernetes non usa dockerd)
- Il shim isola il ciclo di vita del container da quello del daemon: riavviare `dockerd` non termina i container
- `runc` è intercambiabile (gVisor, Kata, Railcar implementano la stessa OCI Runtime Spec)

---

## Linux Namespaces — Isolamento dei Processi

I **namespace** sono la primitiva fondamentale che crea l'isolamento nei container. Ogni container riceve una vista isolata delle risorse di sistema.

```
Linux Namespaces per Container

  Host System
  +---------------------------------------------------------+
  |                                                         |
  |  PID Namespace (container):                             |
  |    Container vede:  PID 1 (app), PID 2 (worker)        |
  |    Host vede:       PID 7421,    PID 7422               |
  |                                                         |
  |  NET Namespace (container):                             |
  |    Container vede:  eth0 (172.17.0.2), lo              |
  |    Host vede:       veth7a3b2c (bridge docker0)         |
  |                                                         |
  |  MNT Namespace (container):                             |
  |    Container vede:  / (rootfs dal layer image)          |
  |    Host vede:       /var/lib/docker/overlay2/...        |
  |                                                         |
  |  UTS Namespace (container):                             |
  |    Container vede:  hostname = "my-container"           |
  |    Host vede:       hostname = "worker-node-1"          |
  |                                                         |
  |  IPC Namespace (container):                             |
  |    Container ha semafori/shared memory propri           |
  |    Non condivisi con altri container                    |
  |                                                         |
  |  USER Namespace (opzionale, rootless):                  |
  |    Container vede:  UID 0 (root) dentro il container    |
  |    Host vede:       UID 100000 (non-privileged)         |
  |                                                         |
  |  CGROUP Namespace (container):                          |
  |    Container vede:  / come root del suo cgroup tree     |
  |    Nasconde la gerarchia host ai processi container     |
  +---------------------------------------------------------+
```

```bash
# Ispeziona i namespace di un container in esecuzione
CONTAINER_PID=$(docker inspect --format '{{.State.Pid}}' my-container)

# Lista namespace del processo container
ls -la /proc/$CONTAINER_PID/ns/
# lrwxrwxrwx cgroup -> cgroup:[4026532456]
# lrwxrwxrwx ipc    -> ipc:[4026532453]
# lrwxrwxrwx mnt    -> mnt:[4026532451]
# lrwxrwxrwx net    -> net:[4026532457]
# lrwxrwxrwx pid    -> pid:[4026532454]
# lrwxrwxrwx uts    -> uts:[4026532452]
# lrwxrwxrwx user   -> user:[4026531837]  ← stesso dell'host se non rootless

# Entra nel namespace di rete del container dall'host
nsenter --target $CONTAINER_PID --net ip addr
# Mostra le interfacce di rete come le vede il container

# Confronta con il namespace di rete dell'host
ls /proc/1/ns/net   # namespace PID 1 = init = host
```

**Il namespace USER** — Fondamento per Rootless Docker:

```bash
# Con User Namespaces (rootless Docker):
# UID 0 (root) dentro il container → mappato a UID 100000+ sull'host

# /proc/$CONTAINER_PID/uid_map:
# 0 100000 65536
# └─┬──┘ └──┬──┘ └──┬──┘
#   0 in    100000  65536 IDs
#   container  sull'host  mappati

# Verifica: un container "root" non è root sull'host
docker run --rm alpine id         # uid=0(root)
docker inspect --format '{{.State.Pid}}' <container>
cat /proc/<PID>/status | grep Uid # Uid: 100000 100000 100000 100000
```

---

## cgroups v2 — Resource Accounting e Limiting

I **cgroups** (control groups) sono il meccanismo del kernel per limitare, misurare e isolare l'uso delle risorse hardware (CPU, memoria, I/O) tra gruppi di processi.

```
cgroups v2 Hierarchy per Container

  /sys/fs/cgroup/
  └── system.slice/
      └── docker-<container-id>.scope/
          ├── cpu.max          "100000 100000" = 100% di 1 CPU
          ├── cpu.weight       100 (default, range 1-10000)
          ├── memory.max       268435456 (256MB)
          ├── memory.swap.max  0 (nessun swap)
          ├── io.max           "8:0 rbps=10485760 wbps=10485760"
          ├── pids.max         100 (max processi nel container)
          └── cgroup.procs     [7421, 7422]  (PIDs nel gruppo)
```

```bash
# docker run con resource limits → cgroups v2
docker run \
    --cpus="1.5" \           # 1.5 core → cpu.max = "150000 100000"
    --cpu-shares=512 \       # peso relativo → cpu.weight
    --memory="256m" \        # memory.max
    --memory-swap="256m" \   # memory + swap = 256m → nessun swap extra
    --pids-limit=100 \       # pids.max
    --blkio-weight=500 \     # io.weight
    nginx

# Leggi live resource usage
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/cpu.stat
# usage_usec 1234567      ← CPU usata in microsecondi
# user_usec  987654
# system_usec 246913
# nr_throttled 0          ← quante volte è stato throttlato
# throttled_usec 0

# Memory pressure
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.pressure
# some avg10=0.00 avg60=0.00 avg300=0.00 total=0
# full avg10=0.00 avg60=0.00 avg300=0.00 total=0
```

**Differenze cgroups v1 vs v2:**

| | cgroups v1 | cgroups v2 |
|---|---|---|
| **Gerarchia** | Controller separati (cpu, memory, blkio) | Gerarchia unificata |
| **CPU throttling** | CFS con cpu.cfs_quota_us | cpu.max (quota/period) |
| **Memory OOM** | Behavior inconsistente | OOM killer migliorato con PSI |
| **I/O accounting** | blkio (solo block) | io (block + filesystem) |
| **Pressure Stall** | Non disponibile | PSI (cpu/memory/io pressure) |
| **Support Docker** | Default su sistemi vecchi | Default da Docker 20.10+ |

---

## Union Filesystem — Come Funzionano i Layer

I container condividono il filesystem usando un **Union Filesystem** (overlay2 su Linux moderno). Questo permette di condividere i layer comuni tra container diversi.

```
overlay2 — Come i Layer si Compongono

  Image: nginx:1.25

  Layer 4 (upperdir, container RW):  [/etc/nginx/nginx.conf modificato]
  ─────────────────────────────────────────────────────────────────
  Layer 3 (image layer):  [/etc/nginx/nginx.conf originale]
  Layer 2 (image layer):  [binari nginx: /usr/sbin/nginx]
  Layer 1 (image layer):  [Debian base: /bin /lib /usr ...]
  ─────────────────────────────────────────────────────────────────
  merged/ (overlayfs mount):  vista unificata dei layer sopra

  Il container vede merged/ come la propria /

  Host filesystem:
  /var/lib/docker/overlay2/
  ├── abc123/  (Layer 1 sha256:...)
  │   └── diff/  (contenuto del layer)
  ├── def456/  (Layer 2)
  │   └── diff/
  ├── ghi789/  (Layer 3)
  │   └── diff/
  └── jkl012/  (Container upper layer - RW)
      ├── diff/     ← scrive qui
      ├── work/     ← overlay2 working dir
      └── merged/   ← mount point finale
```

```bash
# Ispeziona i layer di un'immagine
docker image inspect nginx:1.25 | jq '.[0].RootFS'
# {
#   "Type": "layers",
#   "Layers": [
#     "sha256:a8ca11554fce...",   ← Layer 1
#     "sha256:7a89bf5e2b28...",   ← Layer 2
#     ...
#   ]
# }

# Vedi il mount overlay2 di un container in esecuzione
docker inspect --format '{{json .GraphDriver}}' my-container | jq
# {
#   "Data": {
#     "LowerDir": "/var/lib/docker/overlay2/abc/diff:/var/lib/docker/overlay2/def/diff",
#     "MergedDir": "/var/lib/docker/overlay2/jkl/merged",
#     "UpperDir":  "/var/lib/docker/overlay2/jkl/diff",
#     "WorkDir":   "/var/lib/docker/overlay2/jkl/work"
#   },
#   "Name": "overlay2"
# }

# Dimensione di ogni layer
docker history nginx:1.25 --no-trunc
# IMAGE     CREATED    CREATED BY                SIZE
# sha256... 2 weeks    CMD ["nginx" "-g" ...]    0B
# sha256... 2 weeks    COPY nginx.conf ...       1.2kB
# sha256... 2 weeks    RUN apt-get install...    89.3MB
```

**Copy-on-Write (CoW):**

```
Scrittura in un container (CoW):

  1. Container vuole scrivere /etc/nginx/nginx.conf
  2. overlay2 controlla: il file esiste nell'upper layer?
     NO → fa una copia dal lower layer all'upper layer
  3. Scrive la modifica nella copia in upper layer
  4. Da questo momento, il container vede la versione upper

  IMPLICAZIONE: modificare un file grande (es. database) in un container
  crea una copia completa nell'upper layer → overhead.
  Usare sempre volumes per dati mutabili.
```

---

## OCI Specification — Lo Standard Industriale

**OCI (Open Container Initiative)** definisce due specifiche fondamentali che permettono interoperabilità tra runtime e tool diversi.

### OCI Image Specification

```json
// image manifest (semplificato)
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:abc123...",
    "size": 4096
  },
  "layers": [
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:layer1hash...",
      "size": 29154304
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:layer2hash...",
      "size": 1234567
    }
  ]
}
```

```json
// image config (come viene eseguita l'immagine)
{
  "architecture": "amd64",
  "os": "linux",
  "config": {
    "User": "nobody",
    "ExposedPorts": {"8080/tcp": {}},
    "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"],
    "Cmd": ["/app/server"],
    "WorkingDir": "/app",
    "Labels": {"maintainer": "team@company.com"}
  },
  "rootfs": {
    "type": "layers",
    "diff_ids": ["sha256:layer1uncompressed...", "sha256:layer2uncompressed..."]
  }
}
```

### OCI Runtime Specification

```json
// config.json — cosa runc riceve per creare il container
{
  "ociVersion": "1.0.2",
  "process": {
    "user": {"uid": 0, "gid": 0},
    "args": ["/bin/sh"],
    "env": ["PATH=/usr/local/sbin:..."],
    "cwd": "/",
    "capabilities": {
      "bounding": ["CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_NET_BIND_SERVICE"],
      "permitted": ["CAP_CHOWN", "CAP_DAC_OVERRIDE"],
      "effective": ["CAP_CHOWN"]
    },
    "noNewPrivileges": true,
    "oomScoreAdj": 0,
    "seccomp": {
      "defaultAction": "SCMP_ACT_ERRNO",
      "architectures": ["SCMP_ARCH_X86_64"],
      "syscalls": [
        {"names": ["read", "write", "openat", "close"], "action": "SCMP_ACT_ALLOW"}
      ]
    }
  },
  "root": {"path": "rootfs", "readonly": false},
  "hostname": "my-container",
  "mounts": [
    {"destination": "/proc", "type": "proc", "source": "proc"},
    {"destination": "/dev", "type": "tmpfs", "source": "tmpfs"}
  ],
  "linux": {
    "namespaces": [
      {"type": "pid"}, {"type": "network"}, {"type": "ipc"},
      {"type": "uts"}, {"type": "mount"}, {"type": "cgroup"}
    ],
    "resources": {
      "memory": {"limit": 268435456},
      "cpu": {"quota": 150000, "period": 100000}
    },
    "cgroupsPath": "/docker/container-id"
  }
}
```

---

## Lifecycle di un Container — Dalla CLI al Kernel

```
docker run nginx — Sequenza Completa

  1. docker CLI
     └─► POST /containers/create  (dockerd REST API)

  2. dockerd
     ├─► Pull image se non presente (containerd image store)
     ├─► Crea container metadata
     └─► POST /tasks/create  (containerd gRPC API)

  3. containerd
     ├─► Prepara snapshot (overlay2 layers)
     ├─► Genera OCI bundle (rootfs + config.json)
     └─► Esegue shim: containerd-shim-runc-v2

  4. containerd-shim-runc-v2 (processo persistente)
     └─► runc create --bundle /run/containerd/io.containerd.../bundle

  5. runc
     ├─► clone(CLONE_NEWPID | CLONE_NEWNET | CLONE_NEWNS | ...)  [crea namespaces]
     ├─► mount proc, sysfs, devtmpfs nei nuovi ns
     ├─► pivot_root() → cambia / al rootfs del container
     ├─► Configura cgroups (/sys/fs/cgroup/...)
     ├─► Applica seccomp profile
     ├─► Drop capabilities
     ├─► execve("/usr/sbin/nginx", ...)  → il processo container parte
     └─► runc termina (il shim rimane come monitor)

  6. Il container è in esecuzione
     PID 1 nel container = nginx
     PID 7421 sull'host  = nginx (visibile da /proc)
```

---

## Riferimenti

- [Docker Engine Architecture](https://docs.docker.com/engine/)
- [containerd Architecture](https://containerd.io/docs/getting-started/)
- [OCI Image Spec](https://github.com/opencontainers/image-spec)
- [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec)
- [Linux Namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- [cgroups v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [overlay2 filesystem](https://docs.docker.com/storage/storagedriver/overlayfs-driver/)
