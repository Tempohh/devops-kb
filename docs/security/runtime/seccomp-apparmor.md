---
title: "seccomp e AppArmor — Sandboxing a Runtime"
slug: seccomp-apparmor
category: security
tags: [seccomp, apparmor, runtime-security, container-hardening, syscall-filtering, lsm, linux-security]
search_keywords: [seccomp, apparmor, seccomp profile, seccomp filter, apparmor profile, linux security module, lsm, syscall filtering, seccomp bpf, seccomp strict, seccomp docker, apparmor kubernetes, container hardening, runtime security linux, sandboxing container, capabilities linux, prctl seccomp, seccomp-tools, aa-genprof, apparmor complain mode, apparmor enforce mode, RuntimeDefault seccomp, Localhost seccomp, Unconfined seccomp, seccomp audit, container escape prevention, kernel hardening, pod security context, securityContext seccomp, seccompProfile kubernetes]
parent: security/runtime/_index
related: [containers/container-runtime/sandboxing-avanzato, containers/kubernetes/sicurezza, security/supply-chain/admission-control, containers/docker/sicurezza]
official_docs: https://kubernetes.io/docs/tutorials/security/seccomp/
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# seccomp e AppArmor — Sandboxing a Runtime

## Panoramica

**seccomp** (Secure Computing Mode) e **AppArmor** (Application Armor) sono due meccanismi di hardening a runtime del kernel Linux che riducono drasticamente la superficie di attacco dei container. Operano a livelli diversi e si complementano: seccomp filtra le **system call** che un processo può invocare, AppArmor limita l'accesso a **file, rete e capabilities**.

Un container senza seccomp e AppArmor può invocare qualsiasi delle ~400 syscall Linux disponibili. Questo è eccessivo: un webserver tipico ne usa al massimo 40-50. Le syscall inutilizzate sono potenziali vettori di exploit del kernel (CVE) che permettono il container escape.

| Meccanismo | Livello | Cosa limita | Granularità |
|------------|---------|-------------|-------------|
| seccomp | Syscall layer | Quali syscall il processo può fare | Per syscall, con argomenti (BPF) |
| AppArmor | LSM (kernel) | File, rete, capabilities, mount | Per path, per operazione |
| Capabilities | Kernel | Privilegi root granulari | Per capability |

I tre meccanismi operano in modo indipendente e additivo — tutti e tre attivi danno la maggiore protezione.

!!! warning "Non sostituiscono i sandbox runtime"
    seccomp e AppArmor hardenano il container standard (`runc`). Non sostituiscono sandbox runtime completi come gVisor o Kata Containers per workload altamente untrusted. Usali insieme: seccomp/AppArmor per tutti i container, sandbox VM-based solo per i workload che richiedono isolamento hardware.

---

## seccomp — System Call Filtering

### Come Funziona

seccomp intercetta le syscall **prima** che raggiungano il kernel. Il filtro è un programma BPF (Berkeley Packet Filter) compilato che viene eseguito in kernel space ogni volta che il processo tenta una syscall.

```
Processo Container
    │
    │ syscall(SYS_clone, ...)
    │
    ▼
seccomp filter (BPF program in kernel)
    │
    ├─ ALLOW  → kernel esegue la syscall
    ├─ ERRNO  → ritorna errore al processo (es. EPERM)
    ├─ KILL   → termina il processo
    └─ TRAP   → segnala il tracciante (usato da gVisor)

Il filtro viene valutato in O(n) per ogni syscall.
Per profili grandi usare seccomp BPF con alberi di decisione.
```

seccomp può operare in due modalità:
- **SECCOMP_MODE_STRICT**: permette solo `read`, `write`, `exit`, `sigreturn`. Utile solo per casi specializzati.
- **SECCOMP_MODE_FILTER** (BPF): permette di definire un filtro arbitrario — la modalità usata da Docker/Kubernetes.

### Profili seccomp in Docker

Docker applica di default il profilo `moby/default` che blocca ~44 syscall pericolose su ~400 disponibili.

```bash
# Visualizza il profilo default di Docker
docker run --rm alpine cat /proc/self/status | grep Seccomp
# Seccomp: 2   ← 2 = SECCOMP_MODE_FILTER (profilo attivo)

# Profilo default Docker: cosa viene bloccato
# (lista parziale delle syscall negate)
# keyctl        → accesso ai kernel keys (privilege escalation)
# add_key       → aggiunta chiavi kernel
# request_key   → richiesta chiavi kernel
# ptrace        → debug di processi (lateral movement)
# personality   → cambia la personalità del processo ABI
# acct          → process accounting (richiede root)
# settimeofday  → set system time
# mount         → monta filesystem
# umount2       → smonta filesystem
# pivot_root    → cambia root filesystem
# swapon/swapoff → gestione swap
# reboot        → reboot sistema
# syslog        → accesso ai log kernel
# kexec_load    → carica nuovo kernel

# Esegui con profilo custom
docker run --rm \
  --security-opt seccomp=/path/to/profile.json \
  alpine sh

# Disabilita seccomp (non fare mai in produzione)
docker run --rm \
  --security-opt seccomp=unconfined \
  alpine sh
```

### Profilo seccomp Custom

Il formato JSON del profilo seccomp:

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": [
    "SCMP_ARCH_X86_64",
    "SCMP_ARCH_X86",
    "SCMP_ARCH_X32"
  ],
  "syscalls": [
    {
      "names": [
        "accept", "accept4", "access", "arch_prctl",
        "bind", "brk", "capget", "capset",
        "chdir", "chmod", "chown", "clone",
        "close", "connect", "dup", "dup2",
        "epoll_create", "epoll_create1", "epoll_ctl", "epoll_wait",
        "execve", "exit", "exit_group",
        "fchmod", "fchown", "fcntl", "fstat",
        "futex", "getcwd", "getdents", "getdents64",
        "getpid", "getrandom", "getuid", "getgid",
        "ioctl", "kill", "listen",
        "lseek", "madvise", "mkdir", "mmap", "mprotect",
        "munmap", "nanosleep", "newfstatat", "open", "openat",
        "pipe", "pipe2", "poll", "prctl", "pread64",
        "read", "readlink", "recv", "recvfrom", "recvmsg",
        "rename", "rt_sigaction", "rt_sigprocmask", "rt_sigreturn",
        "select", "send", "sendmsg", "sendto",
        "set_tid_address", "setgid", "setuid",
        "sigaltstack", "socket", "stat", "statfs",
        "uname", "unlink", "wait4", "write", "writev"
      ],
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": ["ptrace"],
      "action": "SCMP_ACT_ALLOW",
      "comment": "Richiesto da alcuni debugger — rimuovere in produzione"
    }
  ]
}
```

!!! tip "Allowlist vs Denylist"
    Preferisci sempre la strategia **allowlist** (`defaultAction: SCMP_ACT_ERRNO` + lista di syscall permesse) alla denylist. Una denylist richiede di conoscere tutte le syscall pericolose — impossibile essere esaustivi. Una allowlist parte da zero e permette solo ciò che è necessario.

### seccomp in Kubernetes

Kubernetes supporta seccomp nativamente dal v1.19 (GA). Si configura nel `securityContext` del pod.

```yaml
# Pod con profilo seccomp RuntimeDefault
apiVersion: v1
kind: Pod
metadata:
  name: my-app
  namespace: production
spec:
  securityContext:
    seccompProfile:
      type: RuntimeDefault    # Profilo default del container runtime (containerd/cri-o)
  containers:
  - name: app
    image: my-registry.io/myapp:v1.2.3
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
```

```yaml
# Pod con profilo seccomp custom (Localhost)
# Il file deve esistere su ogni nodo in:
# /var/lib/kubelet/seccomp/profiles/myapp-restricted.json
apiVersion: v1
kind: Pod
metadata:
  name: my-app-strict
spec:
  securityContext:
    seccompProfile:
      type: Localhost
      localhostProfile: profiles/myapp-restricted.json
  containers:
  - name: app
    image: my-registry.io/myapp:v1.2.3
```

I tre tipi di `seccompProfile.type`:

| Tipo | Descrizione | Raccomandato |
|------|-------------|--------------|
| `RuntimeDefault` | Profilo default del runtime (containerd o cri-o) | ✅ Baseline per tutti i pod |
| `Localhost` | File JSON custom sul nodo | ✅ Per workload che richiedono profilo specifico |
| `Unconfined` | Nessun filtro seccomp | ❌ Solo per debug/diagnostica |

### Generare un Profilo seccomp con oci-seccomp-bpf-hook

```bash
# Installa oci-seccomp-bpf-hook (registra le syscall usate durante l'esecuzione)
# Su Fedora/RHEL:
dnf install -y oci-seccomp-bpf-hook

# Esegui il container con recording abilitato
# Il profilo viene scritto nel path specificato
podman run \
  --annotation io.containers.trace-syscall=of:/tmp/myapp-seccomp.json \
  my-registry.io/myapp:v1.2.3 \
  /app/server --mode=production

# Poi lancia il profilo registrato
cat /tmp/myapp-seccomp.json | python3 -m json.tool | head -50

# Oppure con Docker + seccomp-tools
# pip install seccomp-tools
seccomp-tools dump ./myapp
```

```bash
# Alternativa: usa strace per identificare le syscall (più invasivo)
strace -c -f -e trace=all \
  docker run --rm --security-opt seccomp=unconfined \
  my-registry.io/myapp:v1.2.3 /app/server &

# Output strace:
# % time     seconds  usecs/call     calls    errors syscall
# ─────────────────────────────────────────────────────
#  28.45    0.001234          12       102           read
#  18.32    0.000795           8        99           write
#  12.11    0.000525           5       105           epoll_wait
# ...
# Usa questa lista per costruire l'allowlist del profilo
```

---

## AppArmor — Mandatory Access Control

### Come Funziona

AppArmor è un **Linux Security Module (LSM)** che implementa il Mandatory Access Control (MAC). A differenza del DAC (Discretionary Access Control, i normali permessi Unix), il MAC non può essere aggirato dall'utente root del container.

AppArmor definisce **profili** che specificano cosa un processo può fare in termini di:
- Accesso a file e directory (read/write/execute/lock/link)
- Capacità di rete (network tcp, udp, raw)
- Capabilities (cap_net_bind_service, cap_sys_admin, etc.)
- Mount operations
- Signal handling
- Ptrace

```
Processo Container (anche root)
    │
    │ open("/etc/shadow", O_RDONLY)
    │
    ▼
AppArmor LSM hook
    │
    ├─ Profilo ha regola "/etc/shadow r"  → ALLOW
    ├─ Profilo non ha regola per questo path → DENY (enforce mode)
    └─ Complain mode → ALLOW + log
```

### Profili AppArmor per Container

```bash
# Visualizza i profili AppArmor caricati
aa-status
# apparmor module is loaded.
# 35 profiles are loaded.
# 33 profiles are in enforce mode.
# 2 profiles are in complain mode.
# /usr/sbin/mysqld
# docker-default

# Il profilo "docker-default" è applicato da Docker a ogni container
# per default (se AppArmor è disponibile sul nodo)
cat /etc/apparmor.d/docker
# o
apparmor_parser -p docker-default

# Visualizza un profilo caricato
cat /proc/1/attr/current
# docker-default (enforce)
```

```
# Struttura di un profilo AppArmor per container
# File: /etc/apparmor.d/myapp-profile

#include <tunables/global>

profile myapp-container flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  # Rete: permetti solo TCP outbound su porte specifiche
  network tcp,
  network udp,
  deny network raw,        # Blocca raw socket (port scanning)
  deny network packet,     # Blocca packet socket

  # Filesystem: allowlist esplicita
  /app/**                  r,     # app dir: solo lettura
  /app/server              ix,    # binary: eseguibile
  /tmp/**                  rw,    # tmp: lettura/scrittura
  /var/log/myapp/**        rw,    # log: lettura/scrittura
  /etc/ssl/certs/**        r,     # certificati TLS: solo lettura
  /etc/resolv.conf         r,     # DNS config: solo lettura
  /proc/sys/kernel/random/uuid  r,  # UUID generation

  # Nega esplicitamente paths sensibili
  deny /etc/shadow         rwklx,
  deny /etc/passwd w,
  deny /proc/sysrq-trigger rwklx,
  deny @{PROC}/sys/kernel/** w,

  # Capabilities: solo quelle necessarie
  capability net_bind_service,   # Bind porte < 1024
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability sys_module,

  # Mount: nessun mount permesso
  deny mount,
  deny umount,
  deny pivot_root,

  # Signal: solo al proprio gruppo
  signal (send, receive) peer=myapp-container,
}
```

### AppArmor in Docker e Kubernetes

```bash
# Docker: applica profilo custom
apparmor_parser -r -W /etc/apparmor.d/myapp-profile  # carica il profilo

docker run \
  --security-opt "apparmor=myapp-container" \
  my-registry.io/myapp:v1.2.3

# Verifica profilo applicato
docker inspect <container-id> | jq '.[0].HostConfig.SecurityOpt'
# ["apparmor=myapp-container"]

# Disabilita AppArmor per debug (non fare in produzione)
docker run \
  --security-opt "apparmor=unconfined" \
  my-registry.io/myapp:v1.2.3
```

```yaml
# Kubernetes: applica profilo AppArmor via annotation
# Nota: da K8s 1.30+ è supportato anche nel securityContext
apiVersion: v1
kind: Pod
metadata:
  name: my-app
  annotations:
    # Formato: container.apparmor.security.beta.kubernetes.io/<container-name>
    container.apparmor.security.beta.kubernetes.io/app: localhost/myapp-container
spec:
  containers:
  - name: app
    image: my-registry.io/myapp:v1.2.3
```

```yaml
# Kubernetes 1.30+: AppArmor nel securityContext (API stabile)
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  containers:
  - name: app
    image: my-registry.io/myapp:v1.2.3
    securityContext:
      appArmorProfile:
        type: Localhost            # Localhost | RuntimeDefault | Unconfined
        localhostProfile: myapp-container   # nome profilo caricato sul nodo
```

### Generare un Profilo con aa-genprof

```bash
# aa-genprof: profiling interattivo (genera il profilo da zero)
# 1. Installa AppArmor utils
apt-get install -y apparmor-utils   # Debian/Ubuntu
dnf install -y apparmor-utils       # Fedora (se AppArmor installato)

# 2. Avvia il profiling (in complain mode)
aa-genprof /app/server
# AppArmor profiling mode for /app/server is now enabled.
# Avvia il binario in un altro terminale, fai le operazioni normali

# 3. Nel terminale di profiling, premi S per scansionare i log
# AppArmor suggerisce le regole per ogni accesso rilevato

# 4. Rivedi e salva il profilo
# Il profilo viene salvato in /etc/apparmor.d/

# Alternativa: aa-logprof per aggiornare profili esistenti basandosi sui log
aa-logprof
# Analizza /var/log/audit/audit.log o /var/log/syslog
# Propone regole da aggiungere per gli accessi negati/loggati
```

```bash
# Workflow consigliato per produzione:
# 1. Avvia in complain mode per raccogliere accessi reali
aa-complain /etc/apparmor.d/myapp-container

# 2. Esegui workload reale per 24-48h
# 3. Analizza i log
grep "apparmor=" /var/log/audit/audit.log | grep "myapp-container"
# type=AVC ... apparmor="ALLOWED" operation="open" profile="myapp-container"
#   name="/etc/ssl/certs/ca-certificates.crt" ...

# 4. Aggiorna il profilo con aa-logprof
aa-logprof

# 5. Passa a enforce mode
aa-enforce /etc/apparmor.d/myapp-container
aa-status | grep myapp
```

---

## Configurazione & Pratica

### Hardening Completo di un Pod Kubernetes

```yaml
# Pod completamente hardenato: seccomp + AppArmor + capabilities + context
apiVersion: v1
kind: Pod
metadata:
  name: production-app
  namespace: production
  annotations:
    # AppArmor (pre K8s 1.30)
    container.apparmor.security.beta.kubernetes.io/app: localhost/production-app-profile
spec:
  securityContext:
    # seccomp a livello pod (default per tutti i container)
    seccompProfile:
      type: RuntimeDefault
    # Non-root obbligatorio
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    # Previeni privilege escalation tramite setuid/setgid
    supplementalGroups: [1000]

  containers:
  - name: app
    image: my-registry.io/myapp:v1.2.3
    securityContext:
      # Drop tutte le capabilities, aggiungi solo quelle necessarie
      capabilities:
        drop: ["ALL"]
        add: ["NET_BIND_SERVICE"]   # Solo se bind a porta < 1024
      # Filesystem read-only (scritture solo su volume mounts espliciti)
      readOnlyRootFilesystem: true
      # No setuid/setgid binaries
      allowPrivilegeEscalation: false
      # seccomp override per questo container (più restrittivo del default pod)
      seccompProfile:
        type: Localhost
        localhostProfile: profiles/myapp-strict.json

    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: logs
      mountPath: /var/log/app

  volumes:
  - name: tmp
    emptyDir:
      medium: Memory        # tmpfs in RAM, non su disco
      sizeLimit: 100Mi
  - name: logs
    emptyDir: {}
```

### DaemonSet per Distribuire Profili seccomp sui Nodi

```yaml
# I profili Localhost seccomp devono essere su ogni nodo
# in /var/lib/kubelet/seccomp/profiles/
# Usa un DaemonSet per distribuirli automaticamente
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: seccomp-profile-distributor
  namespace: kube-system
spec:
  selector:
    matchLabels:
      app: seccomp-profiles
  template:
    metadata:
      labels:
        app: seccomp-profiles
    spec:
      initContainers:
      - name: install-profiles
        image: my-registry.io/seccomp-profiles:v1.0.0
        command: ["cp", "-r", "/profiles/.", "/host-seccomp/"]
        volumeMounts:
        - name: seccomp-dir
          mountPath: /host-seccomp
      containers:
      - name: pause
        image: gcr.io/google_containers/pause:3.1
      volumes:
      - name: seccomp-dir
        hostPath:
          path: /var/lib/kubelet/seccomp/profiles
          type: DirectoryOrCreate
      tolerations:
      - operator: Exists     # Gira su tutti i nodi inclusi master
```

---

## Best Practices

- **Inizia con `RuntimeDefault`**: il profilo default di containerd/cri-o blocca già ~44 syscall pericolose con zero configurazione. Applica `RuntimeDefault` a tutti i pod come baseline obbligatoria via Kyverno/OPA Gatekeeper.
- **AppArmor in complain mode prima di enforce**: un profilo troppo restrittivo rompe l'applicazione in produzione. Usa sempre il ciclo complain → profiling → logprof → enforce.
- **Profili custom per workload critici**: per applicazioni che gestiscono dati sensibili (payment, PII), crea profili custom con allowlist minimale invece di usare `RuntimeDefault`.
- **Non disabilitare mai in produzione**: `seccomp=unconfined` o `apparmor=unconfined` eliminano la protezione completamente. Se un'applicazione richiede privilegi eccezionali, crea un profilo specifico, non disabilitare tutto.
- **Audit trail**: abilita l'auditing AppArmor e seccomp nei log di sistema per rilevare tentativi di syscall negate (potenziale exploitation attempt).

!!! tip "Policy enforcement con Kyverno"
    Usa Kyverno o OPA Gatekeeper per rendere obbligatorio `seccompProfile: RuntimeDefault` su tutti i pod del cluster. Impedisce il deploy di workload `Unconfined` senza un'eccezione esplicita e approvata.

    ```yaml
    # Kyverno: richiedi seccomp RuntimeDefault o Localhost
    apiVersion: kyverno.io/v1
    kind: ClusterPolicy
    metadata:
      name: require-seccomp-profile
    spec:
      validationFailureAction: Enforce
      rules:
      - name: check-seccomp
        match:
          any:
          - resources:
              kinds: ["Pod"]
              namespaces: ["production", "staging"]
        validate:
          message: "Tutti i pod devono avere seccompProfile RuntimeDefault o Localhost"
          pattern:
            spec:
              securityContext:
                seccompProfile:
                  type: "RuntimeDefault | Localhost"
    ```

!!! warning "Compatibilità AppArmor per nodo"
    AppArmor non è disponibile su tutti i nodi Kubernetes. RHEL/CentOS usano SELinux (alternativa a AppArmor), Ubuntu/Debian usano AppArmor. In cluster misti, i pod con profilo AppArmor `Localhost` falliscono su nodi SELinux. Usa `nodeSelector` o `nodeAffinity` per indirizzare questi pod solo su nodi con AppArmor abilitato.

---

## Troubleshooting

### 1. Container non si avvia — "operation not permitted" con seccomp

**Sintomo:**
```
Error: container_linux.go:345: starting container process caused "process_linux.go:
430: container init caused \"rootfs_linux.go:58: mounting \\\"proc\\\" to
rootfs at \\\"/proc\\\" caused \\\"mount through procfs is not allowed\\\"\""
```
o semplicemente il container esce immediatamente con exit code 1 e permissiondenied nei log.

**Causa:** Il profilo seccomp nega una syscall necessaria all'applicazione durante lo startup (es. `clone`, `unshare`, `mount`).

**Soluzione:**
```bash
# 1. Avvia il container in modalità unconfined per identificare le syscall negate
docker run --rm \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  my-registry.io/myapp:v1.2.3

# 2. Se funziona in unconfined, il profilo è troppo restrittivo
# 3. Usa strace per trovare le syscall usate durante startup
docker run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_PTRACE \
  my-registry.io/myapp:v1.2.3 \
  strace -f -e trace=all /app/server 2>&1 | grep -E "ENOSYS|EPERM|EACCES"

# 4. Aggiungi le syscall mancanti al profilo e ricarica
```

### 2. AppArmor — profilo non trovato sul nodo Kubernetes

**Sintomo:**
```
Warning  Failed     Pod     Error: failed to create containerd task:
  failed to create shim: OCI runtime create failed:
  container_linux.go:380: ... apparmor_profile "myapp-container" does not exist
```

**Causa:** Il profilo AppArmor non è caricato sul nodo in cui viene schedulato il pod.

**Soluzione:**
```bash
# Sul nodo incriminato: verifica i profili caricati
ssh node-1
aa-status | grep myapp
# (nessun output = profilo non presente)

# Carica il profilo manualmente per test
apparmor_parser -r -W /etc/apparmor.d/myapp-container

# Per soluzione permanente: usa il DaemonSet distributor (vedi sezione precedente)
# O aggiungi il profilo all'init del nodo (cloud-init, Ansible, ecc.)

# Verifica che il profilo sia correttamente formattato prima del deploy
apparmor_parser --preprocess /etc/apparmor.d/myapp-container
# Exit 0 = OK, altrimenti mostra gli errori di sintassi
```

### 3. AppArmor blocca operazioni legittime in enforce mode

**Sintomo:** L'applicazione funzionava in complain mode ma fallisce in enforce mode. Errori tipo `permission denied` su operazioni normali (es. apertura file di config, connessione TCP).

**Causa:** In complain mode le violazioni vengono loggate ma non bloccate. Qualche accesso necessario non è stato incluso nel profilo.

**Soluzione:**
```bash
# Torna temporaneamente in complain mode
aa-complain /etc/apparmor.d/myapp-container

# Reproduci il problema (esegui le operazioni che falliscono)
# Poi analizza i nuovi log
grep "apparmor" /var/log/audit/audit.log | grep "ALLOWED" | grep "myapp-container" | tail -50

# Aggiorna il profilo con aa-logprof
aa-logprof
# Accetta le regole suggerite per gli accessi loggati

# Torna in enforce mode
aa-enforce /etc/apparmor.d/myapp-container
```

### 4. seccomp — syscall negata in produzione (audit log)

**Sintomo:** L'applicazione gira ma alcune funzionalità falliscono silenziosamente. Nei log audit:
```
type=SECCOMP msg=audit(1711234567.890:1234):
  arch=c000003e syscall=316 compat=0 ip=0x7f1234567890 code=0x7ffc0000
  # syscall 316 = renameat2
```

**Causa:** Il profilo seccomp nega una syscall usata da una dipendenza o dalla JVM/runtime dell'applicazione, non dall'applicazione stessa.

**Soluzione:**
```bash
# Identifica il numero della syscall
# syscall 316 su x86_64:
ausyscall x86_64 316
# renameat2

# Verifica se è effettivamente necessaria
man renameat2   # capisce a cosa serve

# Se necessaria: aggiungi al profilo JSON
# "syscalls": [{"names": ["renameat2"], "action": "SCMP_ACT_ALLOW"}]

# Abilita l'audit per seccomp (kernel log)
# In /etc/audit/audit.rules:
# -a always,exit -F arch=b64 -S all -F key=seccomp-audit

# Monitora in tempo reale le syscall negate
auditctl -a always,exit -F arch=b64 -S all -F key=sc-deny
ausearch -k sc-deny --format text | tail -20
```

---

## Relazioni

seccomp e AppArmor si integrano con gli altri meccanismi di sicurezza della KB:

??? info "Sandboxing Avanzato (gVisor, Kata Containers)"
    seccomp e AppArmor hardenano il runtime standard `runc`. Per workload altamente untrusted, combina con sandbox VM-based: gVisor usa internamente seccomp per filtrare le syscall che il Sentry passa al kernel host, mentre Kata Containers isola al livello di virtualizzazione hardware.

    **Approfondimento →** [Sandboxing Avanzato](../../containers/container-runtime/sandboxing-avanzato.md)

??? info "Admission Control — Enforcement al Deploy"
    Usa Kyverno o OPA Gatekeeper per richiedere seccomp `RuntimeDefault` su tutti i pod. L'enforcement al deploy complementa l'hardening runtime: impedisce che workload non protetti arrivino in produzione.

    **Approfondimento →** [Admission Control](../supply-chain/admission-control.md)

??? info "Kubernetes Security Context"
    seccomp e AppArmor sono configurati nel `securityContext` del pod. Lo stesso contesto include capabilities, `runAsNonRoot`, `readOnlyRootFilesystem` — tutti meccanismi che operano insieme per il defense in depth.

    **Approfondimento →** [Kubernetes Sicurezza](../../containers/kubernetes/sicurezza.md)

---

## Riferimenti

- [Kubernetes — seccomp Tutorial](https://kubernetes.io/docs/tutorials/security/seccomp/)
- [Kubernetes — AppArmor](https://kubernetes.io/docs/tutorials/security/apparmor/)
- [Docker — seccomp security profiles](https://docs.docker.com/engine/security/seccomp/)
- [Docker — AppArmor security profiles](https://docs.docker.com/engine/security/apparmor/)
- [AppArmor Documentation](https://apparmor.net/)
- [Linux man page — seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html)
- [CNCF — Kubernetes Hardening Guidance (NSA/CISA)](https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF)
