---
title: "Docker Sicurezza"
slug: sicurezza
category: containers
tags: [docker, sicurezza, rootless, capabilities, seccomp, apparmor, selinux, namespace-escape, supply-chain]
search_keywords: [docker security hardening, rootless docker, linux capabilities containers, seccomp docker profile, apparmor docker, container escape vulnerability, docker daemon socket security, docker bench security, user namespace remapping, docker read-only filesystem, privileged container risks]
parent: containers/docker/_index
related: [containers/docker/architettura-interna, containers/kubernetes/sicurezza, security/supply-chain/image-scanning]
official_docs: https://docs.docker.com/engine/security/
status: reviewed
difficulty: expert
last_updated: 2026-10-04
last_verified: 2026-10-04
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
  User Namespace (range da /etc/subuid, /etc/subgid):
    Container UID 0 (root) → Host UID 1000 (bob stesso!)
    Container UID 1        → Host UID 100000 (primo subUID di bob)
    Container UID 2        → Host UID 100001
    ...

  /proc/<pid-dockerd>/uid_map:
  0     1000      1
  1  100000  65536

  Limitazioni rootless:
  - No binding su porte < 1024 (workaround: sysctl net.ipv4.ip_unprivileged_port_start=80)
  - Overlay2 nativo richiede kernel recente (>= 5.11); su kernel più vecchi serve fuse-overlayfs
  - No macvlan / ipvlan (richiedono CAP_NET_ADMIN sull'host)
  - Rete in user-space (RootlessKit + slirp4netns/pasta): throughput inferiore al bridge rootful
```

!!! note "Perché il root del container è l'utente stesso"
    In rootless, `newuidmap` mappa l'UID 0 del namespace sull'UID reale dell'utente: un container escape ottiene solo i privilegi di `bob`, non di root. Con `userns-remap` (rootful) il daemon resta root, ma il root dei container è mappato su un range subUID senza privilegi.

**UID Remapping (rootful Docker con user namespaces):**

```json
{
  "userns-remap": "default"
}
```

`/etc/docker/daemon.json` — `"default"` crea automaticamente l'utente `dockremap` (e le righe in `/etc/subuid`/`/etc/subgid`); in alternativa `"userns-remap": "bob"`. JSON non ammette commenti. Nota: `userns-remap` è incompatibile con `--privileged` senza `--userns=host` e con alcune funzioni (es. `--pid=host`).

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
# NET_BIND_SERVICE solo se l'app ascolta su porta < 1024;
# no-new-privileges impedisce escalation via setuid/file capabilities
docker run \
    --cap-drop ALL \
    --cap-add NET_BIND_SERVICE \
    --security-opt no-new-privileges:true \
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

Esempio **illustrativo** di profilo allowlist (rimuovere i commenti `//` prima dell'uso: JSON non li ammette). Questa lista è troppo corta per un container reale: `runc` stesso ha bisogno di syscall (`prctl`, `setns`, `pivot_root`, `clone3`, `futex`...) e un runtime come Go/Java ne usa molte altre. Partire dal profilo default di Docker (`moby/profiles/seccomp/default.json`) e rimuovere/aggiungere, oppure generare la lista tracciando l'app.

```json
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
# (è il default se AppArmor è attivo sull'host)
docker run \
    --security-opt apparmor=docker-default \
    mywebapp

# Verifica AppArmor status
aa-status | grep docker
cat /proc/<container-pid>/attr/current  # profilo AppArmor attivo
```

---

## SELinux — MAC su RHEL/Fedora

Sulle distro Red Hat-like (RHEL, Fedora, Rocky) il MAC è **SELinux**, non AppArmor. Con `"selinux-enabled": true` in `daemon.json` ogni container gira con il tipo `container_t` e un'etichetta MCS (Multi-Category Security) univoca: i container non possono leggere i file l'uno dell'altro né quelli dell'host non etichettati per container.

```bash
# Bind mount: rietichetta il path per il container
#   :z = etichetta condivisa tra più container
#   :Z = etichetta privata a questo container
docker run -v /srv/data:/data:Z myapp

# Non usare :Z su /home, /etc, /usr: rietichetta davvero l'host e può romperlo

# Diagnostica: denial SELinux
sudo ausearch -m AVC -ts recent
# Disabilitare SELinux per un singolo container — solo debug
docker run --security-opt label=disable myapp
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
# - Stessa regola per l'appartenenza al gruppo `docker` sull'host: equivale a root
# - Per CI/CD: build senza daemon root (BuildKit rootless, Buildah) o dind isolato
#   (dind richiede --privileged: va confinato in runner effimeri/VM dedicate)
# - Per monitoring: usare un proxy che filtra l'API (docker-socket-proxy)

# docker-socket-proxy (esposizione limitata del socket)
# CONTAINERS=1 permette GET /containers; EXEC=0 nega docker exec; SERVICES=0 nega Swarm
# Il proxy NON va pubblicato su interfacce esposte: terzi lo userebbero come API Docker
docker run -d \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e CONTAINERS=1 \
    -e SERVICES=0 \
    -e EXEC=0 \
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

# runc CVE-2019-5736 (esempio storico):
# Overwrite del binario runc dall'interno di un container
# → Patch: Docker 18.09.2+ (runc rc6+)
# Meccanismo: /proc/self/exe del processo runc punta al binario runc sull'host;
#   un processo malevolo nel container lo riapre in scrittura mentre runc fa exec
# Mitigazione reale: aggiornare runc; user namespaces/rootless (il container non è root host);
#   SELinux. read-only fs e no-new-privileges NON bastano.
```

!!! warning "Le CVE di runc continuano ad arrivare"
    Il pattern ricorre: **CVE-2024-21626** ("Leaky Vessels", fd della directory host trapelato nel container, fix runc 1.1.12) e tre CVE di fine 2025 (CVE-2025-31133, CVE-2025-52565, CVE-2025-52881, abuso di mount/`/proc` durante la creazione del container). Il confine container non è un confine di sicurezza duro: tenere aggiornati `runc`/`containerd`/Docker Engine e, per workload non fidati, valutare sandbox più forti (gVisor, Kata Containers).

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

# Output (esempio):
# [PASS] 5.4  - Ensure that privileged containers are not used
# [WARN] 4.1  - Ensure that a user for the container has been created
# [WARN] 5.31 - Ensure that the Docker socket is not mounted inside any containers
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

## Troubleshooting

### Scenario 1 — Container si avvia ma l'applicazione fallisce con "Operation not permitted"

**Sintomo:** Il container parte, ma l'applicazione crasha con errori tipo `EPERM`, `permission denied`, o `operation not permitted` su operazioni di rete o filesystem.

**Causa:** `--cap-drop ALL` senza aggiungere le capabilities necessarie. Spesso `NET_BIND_SERVICE` (porte < 1024) o `CHOWN` (script di entrypoint che cambiano owner).

**Soluzione:**

```bash
# Identifica la syscall che fallisce con EPERM (seccomp=unconfined esclude seccomp dalla diagnostica;
# SYS_PTRACE serve a strace dentro il container; l'immagine deve contenere strace)
docker run --rm --cap-drop ALL --cap-add SYS_PTRACE \
    --security-opt seccomp=unconfined \
    myapp strace -f -e trace=all -o /dev/stderr myapp-binary 2>&1 | grep EPERM
# Poi mappare la syscall alla capability (man 7 capabilities): es. chown → CHOWN, bind <1024 → NET_BIND_SERVICE

# Oppure avvia temporaneamente con cap-drop ALL e aggiungi una alla volta
docker run --rm \
    --cap-drop ALL \
    --cap-add NET_BIND_SERVICE \
    --cap-add CHOWN \
    myapp

# Verifica capabilities attuali del container
docker run --rm --cap-drop ALL ubuntu capsh --print
# Le capabilities richieste compaiono nei log come EPERM sulle syscall corrispondenti
```

---

### Scenario 2 — Rootless Docker: "cannot expose privileged port"

**Sintomo:** Con rootless Docker, il container non riesce a fare binding su porte < 1024 (80, 443). Errore: `bind: permission denied`.

**Causa:** In modalità rootless il `bind()` sulla porta pubblicata lo esegue RootlessKit come utente normale sull'host, che non può aprire porte < 1024 (`ip_unprivileged_port_start` = 1024). Capabilities dentro il container (o `setcap` nell'immagine) non cambiano nulla.

**Soluzione:**

```bash
# Opzione 1: abbassare la soglia porte privilegiate sul host
sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80
# Per renderlo persistente:
echo "net.ipv4.ip_unprivileged_port_start=80" | sudo tee /etc/sysctl.d/99-rootless-docker.conf
sudo sysctl --system

# Opzione 2: usare porta alta e mettere un reverse proxy davanti
docker run -p 8080:8080 mywebapp
# poi nginx/traefik su host fa forward da 80 → 8080

# Verifica configurazione rootless
dockerd-rootless-setuptool.sh check
```

---

### Scenario 3 — Seccomp blocca syscall e il container crasha silenziosamente

**Sintomo:** Container si avvia e muore subito senza messaggi di errore chiari, oppure l'app riporta `EPERM`/`Operation not permitted` su una syscall specifica.

**Causa:** Il profilo seccomp (default o custom) blocca una syscall usata dall'applicazione. Con `SCMP_ACT_ERRNO` (default Docker) la syscall fallisce con `EPERM`; solo con azioni `SCMP_ACT_KILL*`/`TRAP` il processo muore con SIGSYS (exit code 159 = 128+31).

**Soluzione:**

```bash
# Verifica se è un problema seccomp disabilitandolo temporaneamente
docker run --security-opt seccomp=unconfined myapp
# Se funziona → il problema è seccomp

# Identifica le syscall usate dall'applicazione con strace
docker run --security-opt seccomp=unconfined --cap-add SYS_PTRACE \
    --rm myapp strace -f -c myapp-binary   # -c: riepilogo delle syscall usate

# Confronta con il profilo seccomp attuale e aggiungi le syscall mancanti
# Syscall comuni mancanti in profili custom:
# - clone3 (nuove versioni glibc)
# - statx (filesystem stats moderno)
# - io_uring_* (I/O asincrono)

# Abilita audit per vedere le syscall bloccate (kernel audit)
sudo ausearch -m SECCOMP | tail -20
```

---

### Scenario 4 — AppArmor nega accesso e l'app non riesce a scrivere su /tmp

**Sintomo:** L'applicazione genera errori di scrittura su `/tmp` o altri path. Il kernel log mostra `apparmor="DENIED"`.

**Causa:** Il profilo AppArmor custom non include permessi di scrittura per i path necessari, oppure il profilo non è stato ricaricato dopo le modifiche.

**Soluzione:**

```bash
# Verifica i deny AppArmor in tempo reale
sudo journalctl -f | grep apparmor
# oppure
sudo dmesg | grep apparmor | tail -20
# Output esempio: apparmor="DENIED" operation="file_mknod" profile="docker-web-profile" name="/tmp/.X11-unix/..."

# Metti il profilo in modalità complain (log senza bloccare) per diagnostica
sudo aa-complain /etc/apparmor.d/docker-web-profile
# Poi riavvia il container e osserva i log per vedere tutti i deny

# Aggiorna il profilo aggiungendo il path mancante
sudo nano /etc/apparmor.d/docker-web-profile
# Aggiungi: /tmp/** rw,

# Ricarica il profilo senza riavviare i container
sudo apparmor_parser -r /etc/apparmor.d/docker-web-profile

# Torna in enforce mode dopo la diagnostica
sudo aa-enforce /etc/apparmor.d/docker-web-profile

# Verifica profilo attivo su un container in esecuzione
cat /proc/$(docker inspect --format '{{.State.Pid}}' mycontainer)/attr/current
```

---

## Riferimenti

- [Docker Security](https://docs.docker.com/engine/security/)
- [Rootless Docker](https://docs.docker.com/engine/security/rootless/)
- [Seccomp Security Profiles](https://docs.docker.com/engine/security/seccomp/)
- [AppArmor Security Profiles](https://docs.docker.com/engine/security/apparmor/)
- [Docker Bench Security](https://github.com/docker/docker-bench-security)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [runc CVE-2019-5736](https://nvd.nist.gov/vuln/detail/CVE-2019-5736)
