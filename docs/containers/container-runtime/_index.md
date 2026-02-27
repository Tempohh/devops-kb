---
title: "Container Runtime"
slug: container-runtime
category: containers
tags: [containerd, cri-o, runc, oci, cri, container-runtime, gvisor, kata]
search_keywords: [container runtime interface CRI, containerd kubernetes, CRI-O openshift, runc OCI runtime, container runtime comparison, containerd vs docker, crictl commands, OCI runtime spec, high-level vs low-level runtime]
parent: containers/_index
related: [containers/docker/architettura-interna, containers/kubernetes/architettura, containers/container-runtime/sandboxing-avanzato]
official_docs: https://containerd.io/docs/
status: complete
difficulty: expert
last_updated: 2026-02-25
---

# Container Runtime

## CRI — Container Runtime Interface

La **CRI (Container Runtime Interface)** è lo standard Kubernetes per comunicare con i container runtime. Separa Kubernetes dal runtime specifico.

```
CRI Ecosystem

  Kubernetes (kubelet)
       |
       | gRPC (CRI API)
       |
  +----+------------------------------+
  |                                   |
  containerd (high-level runtime)   CRI-O (high-level runtime)
  |                                   |
  | OCI Runtime Spec                  | OCI Runtime Spec
  |                                   |
  +--------+----+----------+----------+-------+
           |    |          |                  |
         runc  gVisor   Kata Containers    Firecracker
   (default)  (user-space  (VM-based      (MicroVM)
              kernel)      containers)
```

**CRI API — Operazioni principali:**

```protobuf
// CRI gRPC service definition (semplificato)
service RuntimeService {
  rpc RunPodSandbox(RunPodSandboxRequest) returns (RunPodSandboxResponse);
  rpc StopPodSandbox(StopPodSandboxRequest) returns (StopPodSandboxResponse);
  rpc RemovePodSandbox(RemovePodSandboxRequest) returns (RemovePodSandboxResponse);
  rpc PodSandboxStatus(PodSandboxStatusRequest) returns (PodSandboxStatusResponse);
  rpc CreateContainer(CreateContainerRequest) returns (CreateContainerResponse);
  rpc StartContainer(StartContainerRequest) returns (StartContainerResponse);
  rpc StopContainer(StopContainerRequest) returns (StopContainerResponse);
  rpc ExecSync(ExecSyncRequest) returns (ExecSyncResponse);
  rpc Exec(ExecRequest) returns (ExecResponse);  // per kubectl exec
  rpc Attach(AttachRequest) returns (AttachResponse);
}

service ImageService {
  rpc PullImage(PullImageRequest) returns (PullImageResponse);
  rpc RemoveImage(RemoveImageRequest) returns (RemoveImageResponse);
  rpc ListImages(ListImagesRequest) returns (ListImagesResponse);
}
```

---

## containerd — Il Runtime Standard

**containerd** è il runtime high-level di riferimento per Kubernetes. Docker stesso usa containerd internamente (da Docker 1.11+).

```
containerd Architecture

  kubelet (gRPC CRI)
       |
  containerd daemon
  ├── containerd-shim-runc-v2 (per ogni pod)
  │   ├── runc (crea i container)
  │   └── Persiste indipendentemente dal daemon
  ├── Image Service
  │   ├── Pull/Push (OCI distribution spec)
  │   └── Snapshot Store (overlay2)
  ├── Content Store (layer blobs immutabili)
  ├── Metadata Store (bolt DB)
  └── Namespaces
      ├── k8s.io     ← namespace Kubernetes
      ├── moby       ← namespace Docker
      └── default    ← namespace containerd CLI (ctr)
```

```bash
# containerd CLI (basso livello, principalmente per debug)
ctr images ls              # lista immagini nel namespace default
ctr -n k8s.io images ls    # immagini K8s
ctr -n k8s.io containers list   # container gestiti da K8s

# crictl — tool raccomandato per debug K8s runtime
# (compatibile con qualsiasi CRI: containerd, CRI-O)

# Configurazione crictl (una volta sola)
cat > /etc/crictl.yaml << 'EOF'
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 2
debug: false
EOF

# Comandi crictl equivalenti a docker
crictl ps                    # lista container in esecuzione
crictl ps -a                 # tutti i container inclusi stopped
crictl images                # lista immagini
crictl pull nginx:latest     # pull immagine
crictl logs <container-id>   # log container
crictl exec -it <id> sh      # exec nel container
crictl inspect <id>          # dettaglio container (JSON)
crictl pods                  # lista pod sandbox
crictl inspectp <pod-id>     # dettaglio pod sandbox
crictl stats                 # resource usage
crictl info                  # info runtime

# Debugging: trova container per nome
crictl ps --name myapp
crictl ps -o json | jq '.containers[] | select(.metadata.name | contains("api"))'

# Configurazione containerd (/etc/containerd/config.toml)
cat /etc/containerd/config.toml
# [plugins."io.containerd.grpc.v1.cri"]
#   sandbox_image = "registry.k8s.io/pause:3.9"
#   [plugins."io.containerd.grpc.v1.cri".containerd]
#     snapshotter = "overlayfs"
#     default_runtime_name = "runc"
#     [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
#       runtime_type = "io.containerd.runc.v2"
#       [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
#         SystemdCgroup = true   ← CRITICO per cgroups v2

# Registry mirrors (air-gap / pull-through cache)
# [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
#   [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
#     endpoint = ["https://registry.company.com"]
```

---

## CRI-O — Il Runtime per OpenShift

**CRI-O** è un runtime minimale progettato esclusivamente per Kubernetes/CRI (nessun daemon Docker, nessuna CLI per utenti finali). È il runtime default di OpenShift.

```
CRI-O vs containerd

  containerd:
  - Progetto originariamente Docker
  - Feature-rich (namespace, events, plugins)
  - Usato anche da Docker direttamente
  - Plugin architecture estensibile
  - Default in managed K8s (EKS, GKE, AKS)

  CRI-O:
  - Progettato da zero per K8s CRI
  - Minimalista (solo il necessario per K8s)
  - Nessuna funzionalità non-K8s
  - Segue i cicli di release di Kubernetes (N.N.x = K8s N.N.x)
  - Default in OpenShift, MicroShift
  - Usa podman-style tooling (pinned image policy)
```

```bash
# Su OpenShift (CRI-O):
crictl ps                   # funziona identicamente su CRI-O e containerd
crictl rmi --prune           # cleanup immagini non usate

# Tool specifici CRI-O
systemctl status crio
journalctl -u crio -f

# Configurazione CRI-O (/etc/crio/crio.conf)
# [crio.runtime]
# default_runtime = "runc"
# [crio.runtime.runtimes.runc]
# runtime_path = "/usr/bin/runc"
# [crio.runtime.runtimes.kata]
# runtime_path = "/usr/bin/kata-runtime"
# runtime_type = "vm"

# Storage driver
# [crio.image]
# insecure_registries = []
# [crio.network]
# plugin_dirs = ["/opt/cni/bin"]
```

---

## runc — Il Runtime OCI di Riferimento

**runc** è il low-level runtime che implementa la OCI Runtime Specification. Crea effettivamente i namespace, configura i cgroups ed esegue il processo container.

```bash
# runc usage diretto (raramente necessario, principalmente per debug)
# Richiede un OCI bundle (rootfs/ + config.json)

ls /run/containerd/io.containerd.runtime.v2.task/k8s.io/<pod-id>/
# config.json   rootfs/   log.json   init.pid   address

# Stato dei container
runc state <container-id>

# Esegui comando in un container esistente
runc exec <container-id> ps aux

# runc version (include versione spec OCI supportata)
runc --version
# runc version 1.1.12
# spec: 1.0.2-dev
# go: go1.21.8
# libseccomp: 2.5.4
```

---

## RuntimeClass — Seleziona il Runtime per Pod

Kubernetes usa **RuntimeClass** per permettere ai pod di selezionare un runtime specifico.

```yaml
# RuntimeClass per runc (default)
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: runc
handler: runc       # deve corrispondere al handler in containerd/crio config

---
# RuntimeClass per gVisor
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc      # gVisor usa il binario runsc
scheduling:
  nodeSelector:
    sandboxed: "true"      # solo nodi con gVisor installato

---
# RuntimeClass per Kata Containers
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata-qemu
handler: kata-qemu
scheduling:
  nodeSelector:
    kata: "true"
overhead:
  podFixed:            # overhead fisso della VM Kata
    cpu: "250m"
    memory: "350Mi"
```

```yaml
# Usare RuntimeClass in un pod
spec:
  runtimeClassName: gvisor   # seleziona il runtime isolato
  containers:
    - name: untrusted-app
      image: registry.company.com/untrusted:latest
```

---

## Riferimenti

- [CRI Spec](https://github.com/kubernetes/cri-api)
- [containerd](https://containerd.io/docs/)
- [CRI-O](https://cri-o.io/)
- [runc](https://github.com/opencontainers/runc)
- [crictl](https://github.com/kubernetes-sigs/cri-tools)
- [RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/)
