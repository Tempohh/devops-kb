---
title: "Docker Sicurezza"
slug: sicurezza
category: containers
tags: [docker, sicurezza, rootless, capabilities, seccomp, apparmor, selinux, namespace-escape, supply-chain]
search_keywords: [docker security hardening, rootless docker, linux capabilities containers, seccomp docker profile, apparmor docker, container escape vulnerability, docker daemon socket security, docker bench security, user namespace remapping, docker read-only filesystem, privileged container risks]
parent: containers/docker/_index
related: [containers/docker/architettura-interna, containers/kubernetes/sicurezza, security/supply-chain/image-scanning]
official_docs: https://docs.docker.com/engine/security/
status: complete
difficulty: expert
last_updated: 2026-02-25
---

# Docker Sicurezza

## Il Threat Model dei Container

I container NON sono VM. Condividono il kernel con l'host. La sicurezza è una questione di **riduzione della superficie di attacco** e **defense in depth**.

```
Attack Surface Container Security

  Container Boundary (non un confine di sicurezza duro!)
  +------------------------------------------------------+
  |  Container Process                                    |
  |                                                       |
  |  Vettori di attacco:                                  |
  |  1. Escape via privileged container + /proc/sysrq    |
  |  2. Escape via volume mount di / o /proc             |
  |  3. Escape via socket Docker (/var/run/docker.sock)  |
  |  4. Syscall exploit (runc CVE-2019-5736)             |
  |  5. Kernel exploit (container escapes tramite kernel) |
  +------------------------------------------------------+
          |
  Linux Kernel (SHARED con host e tutti i container)
          |
  Defense Layers:
  ✓ User Namespaces (UID mapping)
  ✓ Linux Capabilities (riduzione privilegi)
  ✓ Seccomp (filtro syscall)
  ✓ AppArmor / SELinux (MAC)
  ✓ cgroups (resource limits, anti-DoS)
  ✓ Read-only filesystem
  ✓ No privileged mode
  ✓ No Docker socket mount
```

---

## Rootless Docker — Eliminare il Daemon Root

Il **Rootless Docker** esegue il daemon e i container completamente come utente non-root, eliminando la classe di attacchi che sfrutta i privilegi del daemon.

```bash
# Installazione rootless (utente non-root)
dockerd-rootless-setuptool.sh install

# Oppure con --force per ambienti non interattivi
curl -fsSL https://get.docker.com/rootless | sh

# Configurazione shell
export PATH=/home/user/bin:$PATH
export DOCKER_HOST=unix:///run/user/1000/docker.sock

# Verifica
docker info | grep "rootless"
# ...
# Security Options: seccomp apparmor rootless
# ...
```

```
Rootless Docker — Come funziona

  Utente: bob (UID 1000)

  dockerd (processo di bob, UID 1000)
      |
      | newuidmap/newgidmap (SUID helpers)
      v
  User Namespace:
    Container UID 0 (root) → Host UID 100000 (subUID di bob)
    Container UID 1 → Host UID 100001
    ...

  /proc/<container-pid>/uid_map:
  0  100000  65536

  Limitazioni rootless:
  - No binding su porte < 1024 (workaround: sysctl net.ipv4.ip_unprivileged_port_start=80)
  - Overlay2 può richiedere fuse-overlayfs su alcuni sistemi
  - No macvlan / ipvlan (richiedono CAP_NET_ADMIN sull'host)
  - Performance I/O leggermente inferiore con fuse-overlayfs
```

**UID Remapping (rootful Docker con user namespaces):**

```json
// /etc/docker/daemon.json
{
  "userns-remap": "default",
  // oppure: "userns-remap": "bob" per mappare al UID di bob
  // "default" crea automaticamente un utente "dockremap"
}
```

---

## Linux Capabilities — Principio del Minimo Privilegio

Il kernel Linux divide i privilegi root in ~40 **capabilities** distinte. Docker fa drop di molte capabilities per default — il principio è che ogni container ha solo le capabilities che gli servono.

```
Capabilities Default Docker (cosa viene mantenuto):
CHOWN, DAC_OVERRIDE, FSETID, FOWNER, MKNOD,
NET_RAW, SETGID, SETUID, SETFCAP, SETPCAP,
NET_BIND_SERVICE, SYS_CHROOT, KILL, AUDIT_WRITE

Capabilities droppate per default (pericolo se aggiunte):
SYS_ADMIN  ← montare filesystem, operazioni di sistema avanzate
            QUESTA è la capability più pericolosa
            docker run --cap-add SYS_ADMIN ≈ root completo sull'host

NET_ADMIN  ← modifica routing, iptables, interfacce
SYS_PTRACE ← debug di altri processi (escape via /proc/<pid>/mem)
SYS_MODULE ← caricare kernel module (escape totale)
DAC_READ_SEARCH ← leggere qualsiasi file ignorando permessi
```

```bash
# Hardening: drop tutte le capabilities, aggiungi solo quelle necessarie
docker run \
    --cap-drop ALL \
    --cap-add NET_BIND_SERVICE \    # se l'app ascolta su porta < 1024
    --security-opt no-new-privileges:true \  # impedisce escalation
    nginx

# Verifica capabilities di un container
docker run --rm ubuntu capsh --print
# Current: = cap_chown,cap_dac_override,...+eip

# Con ALL drop:
docker run --rm --cap-drop ALL ubuntu capsh --print
# Current: =

# Container pienamente sicuro per web app:
docker run \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --read-only \
    --tmpfs /tmp:size=128m \
    --user 1001:1001 \
    mywebapp
```

---

## Seccomp — Filtro delle System Call

**Seccomp** (Secure Computing Mode) usa BPF per filtrare le syscall che un container può chiamare. Docker applica un profilo seccomp di default che blocca ~44 syscall pericolose.

```json
// Profilo seccomp custom — principio allowlist
{
  "defaultAction": "SCMP_ACT_ERRNO",      // blocca tutto per default
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {
      "names": [
        "accept", "accept4", "access", "bind", "brk", "capget", "capset",
        "chdir", "chmod", "chown", "clock_gettime", "clone", "close",
        "connect", "dup", "dup2", "epoll_create", "epoll_create1",
        "epoll_ctl", "epoll_wait", "epoll_pwait",
        "execve", "exit", "exit_group",
        "fchmod", "fchown", "fcntl", "fstat", "fstatfs",
        "futex", "getcwd", "getdents", "getdents64",
        "getgid", "getpid", "getppid", "getuid", "getgroups",
        "listen", "lseek", "lstat", "mmap", "mprotect", "munmap",
        "nanosleep", "newfstatat", "open", "openat", "pipe", "pipe2",
        "poll", "ppoll", "pread64", "pwrite64",
        "read", "readlink", "recv", "recvfrom", "recvmsg",
        "rename", "rt_sigaction", "rt_sigprocmask", "rt_sigreturn",
        "select", "send", "sendto", "sendmsg", "setgid", "setuid",
        "setsockopt", "socket", "socketpair", "stat", "statfs",
        "symlink", "uname", "unlink", "wait4", "write", "writev"
      ],
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": ["kill"],
      "action": "SCMP_ACT_ALLOW",
      "args": [{"index": 1, "value": 15, "op": "SCMP_CMP_EQ"}]
      // Permette solo SIGTERM (15), non SIGKILL o altri
    }
  ]
}
```

```bash
# Applica profilo seccomp custom
docker run \
    --security-opt seccomp=/path/to/seccomp-profile.json \
    myapp

# Profilo unconfined (nessun filtro) — solo per debug
docker run --security-opt seccomp=unconfined myapp

# Verifica il profilo seccomp di un container
docker inspect mycontainer | jq '.[0].HostConfig.SecurityOpt'

# Genera profilo seccomp con strace (identifica le syscall usate)
strace -f -o /tmp/strace.log ./myapp
# poi processa /tmp/strace.log per estrarre le syscall usate
```

---

## AppArmor — Mandatory Access Control

**AppArmor** fornisce MAC (Mandatory Access Control) per limitare ciò che un container può fare a livello di filesystem, rete e capabilities.

```
# Profilo AppArmor per container web (docker-web-profile)

#include <tunables/global>

profile docker-web-profile flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  #include <abstractions/nameservice>

  # Rete: solo TCP su porte specifiche
  network tcp,
  network udp,
  deny network raw,
  deny network netlink,

  # Filesystem: lettura generica
  / r,
  /** r,

  # Filesystem: scrittura solo dove necessario
  /app/data/** rw,
  /tmp/** rw,
  /var/log/app/** w,

  # Nega accesso a path critici
  deny /proc/sys/kernel/** w,
  deny /sys/** w,
  deny /etc/passwd w,
  deny /etc/shadow r,

  # Capabilities
  capability net_bind_service,
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability sys_module,
}
```

```bash
# Carica il profilo AppArmor
apparmor_parser -r -W /etc/apparmor.d/docker-web-profile

# Applica il profilo al container
docker run \
    --security-opt apparmor=docker-web-profile \
    mywebapp

# Profilo default Docker (docker-default)
docker run \
    --security-opt apparmor=docker-default \  # questo è il default
    mywebapp

# Verifica AppArmor status
aa-status | grep docker
cat /proc/<container-pid>/attr/current  # profilo AppArmor attivo
```

---

## Vulnerabilità Critiche — Container Escape

**Il Docker Socket — Il Vettore di Attacco Principale:**

```bash
# ✗ PERICOLOSISSIMO: montare il Docker socket nel container
docker run -v /var/run/docker.sock:/var/run/docker.sock hacker-image
# L'immagine può ora:
# docker run -it --privileged --pid=host --net=host \
#     -v /:/host ubuntu chroot /host
# → Root completo sull'host!

# Limitazioni Docker socket:
# - Non montare mai /var/run/docker.sock in container non fidati
# - Per CI/CD: usare Docker-in-Docker (dind) isolato o Kaniko
# - Per monitoring: usare socket Unix con proxy (docker-socket-proxy)

# docker-socket-proxy (esposizione limitata del socket)
docker run -d \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e CONTAINERS=1 \         # permette GET /containers
    -e SERVICES=0 \           # nega servizi Swarm
    -e EXEC=0 \               # nega docker exec
    tecnativa/docker-socket-proxy
```

**Privileged Mode — Da Non Usare Mai in Produzione:**

```bash
# ✗ Privileged container = nessun isolamento di sicurezza
docker run --privileged myimage
# Cosa ottieni con --privileged:
# - Tutte le capabilities Linux
# - Accesso a /dev (incluso /dev/sda, /dev/mem)
# - Può montare filesystem
# - Può caricare kernel module
# - Effettivamente root sull'host

# Alternativa: dare solo le capabilities specifiche necessarie
# Invece di --privileged per montare un filesystem:
docker run --cap-add SYS_ADMIN --device /dev/fuse myapp

# runc CVE-2019-5736 (esempio historical exploit):
# Overwrite del binario runc dall'interno di un container
# → Patch: runc 1.0.0-rc8+, Docker 18.09.2+
# Meccanismo: /proc/self/exe del container punta al runc binary
# Mitigazione: read-only filesystem, no-new-privileges
```

---

## Docker Bench Security

```bash
# Docker Bench for Security: checklist CIS Docker Benchmark
docker run -it --net host --pid host --userns host --cap-add audit_control \
    -e DOCKER_CONTENT_TRUST=$DOCKER_CONTENT_TRUST \
    -v /etc:/etc:ro \
    -v /usr/bin/containerd:/usr/bin/containerd:ro \
    -v /usr/bin/runc:/usr/bin/runc:ro \
    -v /usr/lib/systemd:/usr/lib/systemd:ro \
    -v /var/lib:/var/lib:ro \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    --label docker_bench_security \
    docker/docker-bench-security

# Output colorato:
# [PASS] 2.1 Ensure the container host has been Hardened
# [WARN] 2.2 Ensure that the Docker daemon is running as a non-root user
# [INFO] 4.1 Ensure that a user for the container has been created
```

---

## Checklist Sicurezza Container

```yaml
# docker-compose.yml — configurazione sicura
services:
  api:
    image: registry.company.com/api:1.0.0@sha256:abc123...  # digest pin
    user: "1001:1001"
    read_only: true
    tmpfs:
      - /tmp:size=128m,mode=1777
      - /run:size=32m
    security_opt:
      - no-new-privileges:true
      - seccomp:./seccomp-profile.json
      - apparmor:docker-api-profile
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE    # solo se necessario
    volumes:
      - app-data:/app/data    # no bind mount su path sensibili
      # MAI: - /var/run/docker.sock:/var/run/docker.sock
      # MAI: - /:/host
      # MAI: - /proc:/proc
    ulimits:
      nproc: 65535
      nofile:
        soft: 1024
        hard: 65535
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 256M       # limita impatto di memory leak
```

**Checklist rapida:**

| Check | Rischio se mancante |
|-------|---------------------|
| Utente non-root | Processi root nel container possono sfruttare kernel exploits |
| `--cap-drop ALL` | Capabilities inutilizzate aumentano la superficie di attacco |
| `no-new-privileges:true` | Processo figlio può acquisire privilegi via setuid |
| `read_only: true` | Attaccante può modificare binari nel container |
| Nessun Docker socket | Container può creare container privilegiati |
| Nessun `--privileged` | Container ha accesso completo al kernel |
| Seccomp profile | Syscall pericolose accessibili (reboot, kexec_load, bpf) |
| Image digest pin | Immagine soggetta a tag mutation (supply chain attack) |
| Resource limits | Container può esaurire risorse host (DoS) |

---

## Riferimenti

- [Docker Security](https://docs.docker.com/engine/security/)
- [Rootless Docker](https://docs.docker.com/engine/security/rootless/)
- [Seccomp Security Profiles](https://docs.docker.com/engine/security/seccomp/)
- [AppArmor Security Profiles](https://docs.docker.com/engine/security/apparmor/)
- [Docker Bench Security](https://github.com/docker/docker-bench-security)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [runc CVE-2019-5736](https://nvd.nist.gov/vuln/detail/CVE-2019-5736)
