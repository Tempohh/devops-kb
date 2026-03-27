---
title: "eBPF — Extended Berkeley Packet Filter"
slug: ebpf
category: networking
tags: [ebpf, kernel, networking, security, observability, cilium, falco, xdp, tracing]
search_keywords: [ebpf, extended bpf, berkeley packet filter, kernel programmability, xdp express data path, tc traffic control, kprobe, uprobe, tracepoint, bpftrace, bpftool, libbpf, bcc tools, cilium ebpf, falco ebpf, tetragon, pixie, hubble, kernel bypass, packet filtering, syscall tracing, performance profiling, network observability, runtime security, container security, kernel modules alternativa, co-re compile once run everywhere, btf bpf type format, bpf maps, ring buffer, verifier ebpf, jit compiler bpf, socket filter, lsm bpf, xdp drop, xdp redirect, cgroup bpf, fentry fexit, raw tracepoint]
parent: networking/fondamentali/_index
related: [networking/kubernetes/cni, containers/kubernetes/sicurezza, security/runtime/seccomp-apparmor, networking/fondamentali/modello-osi]
official_docs: https://ebpf.io/
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# eBPF — Extended Berkeley Packet Filter

## Panoramica

eBPF (Extended Berkeley Packet Filter) è una tecnologia del kernel Linux che permette di eseguire programmi sandbox direttamente nello spazio kernel senza modificare il codice sorgente del kernel stesso e senza caricare moduli kernel. I programmi eBPF vengono verificati staticamente per la safety (nessun loop infinito, nessun accesso out-of-bounds), compilati JIT in istruzioni macchina native, e attaccati a hook points strategici nel kernel — syscall, eventi di rete, tracepoint, funzioni del kernel.

Questa capacità trasforma il kernel Linux in una piattaforma programmabile: invece di dover patchare il kernel o sviluppare kernel module (rischiosi, difficili da mantenere, legati alla versione del kernel), eBPF permette di estendere il comportamento del kernel a runtime in modo sicuro e portabile. È la tecnologia abilitante di Cilium (networking ad alta performance), Falco (runtime security), Tetragon (security enforcement), Pixie (observability automatica), e dei BCC/bpftrace tools per il profiling di sistema.

eBPF è rilevante per DevOps/SRE perché opera nel punto più efficiente della stack: **nel kernel, prima che i dati raggiungano lo userspace**. Questo elimina l'overhead degli approcci tradizionali basati su sidecar o agent userspace, e permette visibilità completa senza modificare le applicazioni.

!!! warning "Requisiti kernel"
    eBPF moderno richiede kernel Linux 5.8+ per le funzionalità complete (ring buffer, BTF, CO-RE). Alcune features (XDP, kprobes base) sono disponibili da Linux 4.x. Su kernel < 4.18 la support è limitata. Su Windows e macOS eBPF non è disponibile nativamente — gli strumenti basati su eBPF richiedono VM Linux o WSL2.

## Concetti Chiave

### Da BPF a eBPF

Il Berkeley Packet Filter originale (1992) era progettato per filtrare pacchetti di rete in modo efficiente. eBPF (2014+, Linux 3.18) ne estende radicalmente le capacità:

| Caratteristica | BPF classico | eBPF |
|---|---|---|
| Registri | 2 × 32-bit | 11 × 64-bit |
| Stack size | 512 byte | 512 byte |
| Istruzioni max | 4096 | 1M (da kernel 5.2) |
| Maps (storage) | No | Sì (hash, array, ring buffer, ...) |
| Helper functions | Minime | 200+ |
| Portabilità (CO-RE) | No | Sì (BTF) |
| Hook points | Solo socket | Kernel-wide (kprobe, XDP, cgroup, LSM, ...) |
| JIT compilation | Opzionale | Default abilitato |

### Architettura di un Programma eBPF

```
  Developer scrive programma C (ristretto) o usa librerie alto livello
           │
           ▼
  Compilato con clang/LLVM → bytecode BPF (.o ELF)
           │
           ▼
  Loader (libbpf / bcc) carica in kernel tramite syscall bpf()
           │
           ▼
  ┌─────────────────────────────────────────────────────┐
  │                    KERNEL SPACE                      │
  │                                                     │
  │  ┌──────────────┐    ┌─────────────────────────┐   │
  │  │   Verifier   │───▶│   JIT Compiler          │   │
  │  │              │    │   (bytecode → macchina)  │   │
  │  │ - Type check │    └────────────┬────────────┘   │
  │  │ - Bounds     │                 │                  │
  │  │ - Terminaz.  │                 ▼                  │
  │  └──────────────┘     Programma eBPF attaccato a    │
  │                        hook point nel kernel         │
  │                                                     │
  │  ┌──────────────────────────────────────────────┐   │
  │  │              BPF Maps (storage)              │   │
  │  │  Hash | Array | RingBuf | PerCPU | LRU | ... │   │
  │  └──────────────────────┬───────────────────────┘   │
  └─────────────────────────┼───────────────────────────┘
                            │ (lettura/scrittura bidirezionale)
                            ▼
                      USERSPACE AGENT
                  (legge metriche, eventi, log)
```

### Il Verifier

Il verifier è il componente che garantisce la safety dei programmi eBPF prima dell'esecuzione. Analizza staticamente ogni possibile percorso di esecuzione e rifiuta programmi che:

- Contengono loop non terminabili (da kernel 5.3 sono ammessi loop limitati verificabili)
- Accedono a memoria fuori dai bounds consentiti
- Dereferenziano puntatori NULL senza controllo
- Chiamano funzioni kernel non permesse per il tipo di programma
- Superano il limite di complessità (istruzioni processed)

Il verifier è la ragione per cui eBPF è sicuro a differenza dei kernel module: un modulo difettoso può crashare il kernel, un programma eBPF viene semplicemente rifiutato.

### Hook Points Principali

```
Kernel Linux — Hook Points eBPF

  ┌─────────────────────────────────────────────────────────────┐
  │  NETWORK PATH                                               │
  │                                                             │
  │  NIC → [XDP hook] → driver → [TC ingress hook]             │
  │       → IP stack → [socket hook] → userspace app           │
  │  userspace app → [socket hook] → [TC egress hook] → NIC    │
  │                                                             │
  │  SYSCALL / KERNEL FUNCTIONS                                 │
  │                                                             │
  │  Syscall entry/exit → [tracepoint hook]                     │
  │  Kernel function entry → [kprobe/fentry hook]               │
  │  Kernel function exit → [kretprobe/fexit hook]              │
  │  Userspace function → [uprobe hook]                         │
  │                                                             │
  │  SECURITY / CGROUPS                                         │
  │                                                             │
  │  LSM hooks → [BPF LSM] (audit, enforce policy)             │
  │  cgroup v2 → [cgroup BPF] (resource, network control)      │
  └─────────────────────────────────────────────────────────────┘
```

| Hook Type | Layer | Uso tipico |
|---|---|---|
| **XDP** | Driver (pre-kernel stack) | DDoS mitigation, load balancing ultra-fast |
| **TC (Traffic Control)** | Network stack L3/L4 | Routing, NAT, policy enforcement (Cilium) |
| **kprobe / fentry** | Kernel functions | Tracing, profiling, debug |
| **tracepoint** | Kernel events stabili | Syscall tracing (openat, connect, execve) |
| **uprobe** | Userspace functions | Tracing applicazioni senza modificarle |
| **LSM** | Linux Security Module | Runtime security enforcement (Tetragon) |
| **cgroup** | Control groups | Network policy per cgroup (container) |
| **socket** | Socket layer | Filtering pacchetti, load balancing L4 |

### BPF Maps

Le BPF Maps sono strutture dati condivise tra programma eBPF (kernel) e userspace. Permettono al programma kernel di accumulare dati (contatori, flow table, eventi) che l'agent userspace legge.

```
  Programma eBPF (kernel)          Userspace Agent
  ────────────────────────         ─────────────────
  bpf_map_update_elem()  ──────▶  bpf_map_lookup_elem()
  bpf_map_lookup_elem()  ◀──────  bpf_map_update_elem()
  bpf_ringbuf_submit()   ──────▶  ring_buffer__poll()
```

| Tipo Map | Struttura | Caso d'uso tipico |
|---|---|---|
| `BPF_MAP_TYPE_HASH` | Hash table | Connection tracking, flow table |
| `BPF_MAP_TYPE_ARRAY` | Array indexato | Contatori per CPU, configurazione |
| `BPF_MAP_TYPE_RINGBUF` | Ring buffer | Stream di eventi da kernel a userspace |
| `BPF_MAP_TYPE_PERCPU_HASH` | Hash per-CPU | Contatori senza lock, alta frequenza |
| `BPF_MAP_TYPE_LRU_HASH` | Hash con eviction LRU | Cache connessioni, bounded memory |
| `BPF_MAP_TYPE_PROG_ARRAY` | Array di programmi eBPF | Tail calls, program chaining |
| `BPF_MAP_TYPE_PERF_EVENT_ARRAY` | Perf events | Profiling CPU, flamegraph |

## Architettura / Come Funziona

### Ciclo di Vita XDP (eXpress Data Path)

XDP è l'hook più veloce perché opera **nel driver della NIC**, prima che il pacchetto entri nello stack di rete del kernel. Permette di prendere decisioni di forwarding/drop a velocità line-rate.

```
  Pacchetto in arrivo
         │
         ▼
  ┌─────────────────────────────────────┐
  │         NIC Driver (kernel)         │
  │                                     │
  │  eBPF XDP Program:                  │
  │  ┌──────────────────────────────┐   │
  │  │  parse eth_hdr, ip_hdr...    │   │
  │  │  if (is_ddos_src(src_ip)):   │   │
  │  │      return XDP_DROP;        │   │ ← Dropped prima del kernel stack!
  │  │  if (needs_redirect(dst)):   │   │
  │  │      return XDP_REDIRECT;    │   │ ← Forwarding diretto altra NIC
  │  │  return XDP_PASS;            │   │ ← Normale processing kernel
  │  └──────────────────────────────┘   │
  └─────────────────────────────────────┘
         │ (solo pacchetti XDP_PASS)
         ▼
  ┌──────────────────┐
  │  Kernel Network  │
  │  Stack (sk_buff) │
  └──────────────────┘
```

**Return codes XDP:**
- `XDP_DROP` — scarta il pacchetto immediatamente (DDoS mitigation: zero overhead)
- `XDP_PASS` — passa il pacchetto al normale stack di rete
- `XDP_TX` — rimanda il pacchetto sulla stessa NIC (reflection, echo server)
- `XDP_REDIRECT` — forwards verso altra NIC o userspace via AF_XDP
- `XDP_ABORTED` — errore nel programma, scarta + incrementa contatore errore

### CO-RE (Compile Once, Run Everywhere)

Il problema storico dei programmi kernel era la dipendenza dalla versione del kernel: un modulo compilato per kernel 5.15 non funzionava su 5.4. CO-RE risolve questo tramite **BTF (BPF Type Format)** — metadati di tipo incorporati nel kernel che permettono al loader di ri-relocare il bytecode eBPF al runtime in base alle strutture dati effettive del kernel corrente.

```bash
# Verifica se il kernel supporta BTF (necessario per CO-RE)
ls /sys/kernel/btf/vmlinux
# Se esiste → CO-RE supportato

# Verifica versione kernel e features eBPF
uname -r
bpftool feature probe | grep -E "program_type|map_type" | head -20
```

## Configurazione & Pratica

### bpftool — Ispezione e Debug

`bpftool` è lo strumento CLI ufficiale per ispezionare e gestire programmi e map eBPF nel kernel.

```bash
# Installa bpftool (su Ubuntu/Debian)
apt-get install linux-tools-$(uname -r) linux-tools-common

# Lista tutti i programmi eBPF attivi nel kernel
bpftool prog list
# Output esempio:
# 42: xdp  name xdp_lb  tag a04f5eef06a7f555  gpl
#         loaded_at 2026-03-25T10:00:00+0000  uid 0
#         xlated 112B  jited 92B  memlock 4096B  map_ids 3,4

# Ispeziona un programma specifico (bytecode tradotto)
bpftool prog dump xlated id 42

# Lista tutte le BPF maps
bpftool map list

# Leggi contenuto di una map
bpftool map dump id 3

# Mostra programmi eBPF attaccati a una NIC (XDP)
bpftool net list dev eth0

# Verifica features eBPF supportate dal kernel corrente
bpftool feature probe

# Genera skeleton C da un programma eBPF compilato
bpftool gen skeleton myprog.o > myprog.skel.h

# Mostra statistiche di esecuzione dei programmi
bpftool prog show id 42 --pretty
```

### bpftrace — Tracing ad Alto Livello

`bpftrace` offre un linguaggio di scripting simile ad awk/DTrace per scrivere programmi eBPF senza C.

```bash
# Installa bpftrace
apt-get install bpftrace   # Ubuntu 20.04+
# oppure da source: https://github.com/bpftrace/bpftrace

# One-liner: traccia tutte le syscall open() con PID e filename
bpftrace -e 'tracepoint:syscalls:sys_enter_openat { printf("%d %s %s\n", pid, comm, str(args->filename)); }'

# Conta syscall per processo (top syscall per 5 secondi poi stampa)
bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); } interval:s:5 { print(@); clear(@); exit(); }'

# Latenza delle system call write() (istogramma)
bpftrace -e '
tracepoint:syscalls:sys_enter_write { @start[tid] = nsecs; }
tracepoint:syscalls:sys_exit_write  /@start[tid]/
{
    @latency_ns = hist(nsecs - @start[tid]);
    delete(@start[tid]);
}'

# Traccia connessioni TCP in uscita (IP + porta)
bpftrace -e 'kprobe:tcp_connect {
    $sk = (struct sock *)arg0;
    printf("connect: %s → %s:%d\n",
        comm,
        ntop(2, $sk->__sk_common.skc_daddr),
        $sk->__sk_common.skc_dport >> 8);
}'

# Profiling CPU: flamegraph dati (stack traces ogni 99Hz per 30s)
bpftrace -e 'profile:hz:99 { @[ustack, kstack] = count(); }' -c "sleep 30" > stacks.bt
# Poi converti con flamegraph.pl per visualizzare
```

### BCC Tools — Toolkit di Sistema

BCC (BPF Compiler Collection) include decine di strumenti pronti all'uso basati su eBPF.

```bash
# Installa BCC tools
apt-get install bpfcc-tools python3-bpfcc

# execsnoop: traccia ogni esecuzione di processo (exec syscall)
execsnoop-bpfcc
# Output: PCOMM   PID    PPID   RET ARGS
#         bash    1234   1200     0 /bin/ls -la

# opensnoop: traccia aperture file con path completo
opensnoop-bpfcc -p 1234  # solo PID 1234

# tcplife: durata connessioni TCP con bytes trasferiti
tcplife-bpfcc
# Output: PID   COMM     LADDR         LPORT RADDR         RPORT TX_KB RX_KB MS

# biolatency: latenza I/O disco (istogramma)
biolatency-bpfcc -D 10  # 10 secondi, per disco

# runqlat: latenza run queue scheduler (quanto aspettano i thread)
runqlat-bpfcc 1 5  # 5 campionamenti da 1 secondo

# funclatency: latenza di qualsiasi funzione kernel
funclatency-bpfcc 'vfs_read'  # latenza vfs_read() in μs

# cachestat: hit rate della page cache Linux
cachestat-bpfcc 1  # aggiorna ogni secondo

# profile: CPU profiling con stack traces (per flamegraph)
profile-bpfcc -F 99 30 > out.stacks  # 99Hz per 30s
```

### Programma eBPF in C con libbpf (Esempio Minimo)

```c
// packet_counter.bpf.c — conta pacchetti per protocollo
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

// Map: protocol (u8) → packet count (u64)
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 256);
    __type(key, __u32);
    __type(value, __u64);
} proto_stats SEC(".maps");

// Programma attaccato a XDP
SEC("xdp")
int count_packets(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (bpf_ntohs(eth->h_proto) != ETH_P_IP)
        return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    __u32 proto = ip->protocol;
    __u64 *count = bpf_map_lookup_elem(&proto_stats, &proto);
    if (count)
        __sync_fetch_and_add(count, 1);  // atomic increment

    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
```

```bash
# Compila il programma eBPF
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
    -I/usr/include/bpf \
    -c packet_counter.bpf.c -o packet_counter.bpf.o

# Carica su eth0 tramite bpftool
bpftool prog load packet_counter.bpf.o /sys/fs/bpf/packet_counter
bpftool net attach xdp pinned /sys/fs/bpf/packet_counter dev eth0

# Leggi i contatori dalla map
bpftool map dump pinned /sys/fs/bpf/proto_stats
```

### eBPF in Kubernetes con Cilium

```bash
# Installa Cilium con kube-proxy replacement completo (usa eBPF al posto di iptables)
cilium install \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=<API_SERVER_IP> \
  --set k8sServicePort=6443

# Verifica che kube-proxy sia sostituito
cilium status | grep -E "KubeProxy|eBPF"
# KubeProxyReplacement: True
# eBPF NodePort:         Enabled

# Abilita Hubble (observability layer su eBPF)
cilium hubble enable --ui

# Visualizza flussi di rete in tempo reale
hubble observe --namespace production --follow

# Flussi verso un servizio specifico
hubble observe --to-service default/frontend --follow

# Service map Hubble (richiede Hubble UI)
cilium hubble ui &
# Apre browser su http://localhost:12000

# Verifica performance: statistiche eBPF
cilium bpf stats list

# Ispeziona le BPF maps di Cilium
cilium bpf lb list          # Load balancer entries
cilium bpf policy get --all # Policy enforcement entries
cilium bpf ct list global   # Connection tracking table
```

### eBPF per Runtime Security con Falco

```bash
# Installa Falco con driver eBPF (nessun kernel module necessario)
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set driver.kind=ebpf \
  --set driver.ebpf.path=/sys/kernel/btf/vmlinux

# Verifica che Falco usi eBPF
kubectl logs -n falco daemonset/falco | grep "eBPF\|driver"
# Using eBPF driver...

# Regola Falco personalizzata: alert su exec in container privilegiato
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-rules-custom
  namespace: falco
data:
  custom_rules.yaml: |
    - rule: Privileged Container Exec
      desc: Detect exec in privileged container
      condition: >
        spawned_process and container and container.privileged=true
        and proc.name != "pause"
      output: >
        Exec in privileged container (user=%user.name cmd=%proc.cmdline
        container=%container.name image=%container.image.repository)
      priority: WARNING
EOF
```

## Best Practices

!!! tip "Scegliere il giusto livello di astrazione"
    Non scrivere programmi eBPF in C raw a meno che non sia strettamente necessario. In ordine di preferenza: **usa uno strumento esistente** (Cilium, Falco, BCC tools) → **usa bpftrace per scripting one-off** → **usa libbpf con CO-RE** solo per programmi custom deployati in produzione.

- **CO-RE obbligatorio per produzione**: usare sempre BTF + CO-RE con libbpf per portabilità kernel. Evitare BCC in produzione (richiede compilatore sul nodo)
- **Limitare la complessità del verifier**: il verifier ha limiti di complexity; preferire helper functions `bpf_*` piuttosto che logica custom complessa. Testare con `bpftool prog verify`
- **Maps bounded**: definire sempre `max_entries` appropriato nelle maps. Maps illimitate causano memory pressure kernel; preferire `BPF_MAP_TYPE_LRU_HASH` per flow tables
- **RingBuffer vs PerfEvent**: preferire `BPF_MAP_TYPE_RINGBUF` (Linux 5.8+) rispetto a perf event array per streaming eventi — minore overhead, no perdita dati per buffer overflow
- **Gestire il fallback**: nei deployment Kubernetes, verificare che il kernel del nodo supporti le features eBPF richieste prima del deploy. Cilium in particolare richiede kernel 5.4+ (minimo) e 5.10+ (raccomandato)
- **Debug incrementale**: durante lo sviluppo usare `bpf_printk()` per debug (output in `/sys/kernel/debug/tracing/trace_pipe`). In produzione rimuovere tutti i `bpf_printk()` — hanno overhead non trascurabile
- **Monitoring dei programmi**: monitorare con `bpftool prog show` e metrics Prometheus esposte da Cilium/Falco — un programma che usa troppo CPU può impattare la latenza del kernel

!!! warning "eBPF non è una sandbox impenetrabile"
    Pur essendo sicuro per il kernel, un programma eBPF legge dati sensibili (syscall arguments, network payloads, process memory). Limitare con Seccomp chi può caricare programmi eBPF (`CAP_BPF` + `CAP_PERFMON` richiesti da kernel 5.8). In ambienti multi-tenant, considerare che Cilium e Falco richiedono privilegi elevati — gestire con PSA (Pod Security Admission) `restricted` profile separato.

## Troubleshooting

### Programma eBPF rifiutato dal verifier

**Sintomo:** `bpftool prog load` fallisce con `libbpf: load bpf object failed` o errori tipo `R1 invalid mem access 'map_value_or_null'`

**Causa:** Il verifier ha trovato un percorso di codice non safe — tipicamente un puntatore non verificato dopo `bpf_map_lookup_elem()` (che può restituire NULL).

```c
// ❌ Sbagliato — verifier rifiuta (NULL dereference possibile)
__u64 *count = bpf_map_lookup_elem(&stats, &key);
*count += 1;  // count potrebbe essere NULL!

// ✅ Corretto — controllo esplicito del NULL
__u64 *count = bpf_map_lookup_elem(&stats, &key);
if (count)
    *count += 1;
```

```bash
# Log dettagliato del verifier (richiede kernel debug)
bpftool prog load myprog.bpf.o /sys/fs/bpf/myprog 2>&1 | head -50

# Aumenta il log level per più dettagli
bpftool -d prog load myprog.bpf.o /sys/fs/bpf/myprog
```

### Programma caricato ma non riceve eventi

**Sintomo:** il programma eBPF è visibile in `bpftool prog list` ma non genera dati.

**Causa:** il programma non è attaccato all'hook point corretto, oppure l'hook è sul nodo sbagliato.

```bash
# Verifica se il programma è attaccato a una NIC
bpftool net list

# Verifica se ci sono programmi attaccati a tracepoints
bpftool perf list

# Verifica se ci sono programmi attaccati via cgroup
bpftool cgroup list /sys/fs/cgroup/

# Riattacca manualmente a eth0
bpftool net attach xdp id <PROG_ID> dev eth0
```

### Cilium: pod non comunicano dopo installazione

**Sintomo:** pod in stato `Running` ma `ping` tra pod su nodi diversi fallisce. `cilium status` mostra errori.

```bash
# Diagnosi rapida
cilium status --verbose
cilium connectivity test  # test suite completa

# Verifica che i daemonset siano tutti Ready
kubectl get pods -n kube-system -l k8s-app=cilium
kubectl describe pod -n kube-system <cilium-pod> | tail -30

# Controlla i log di Cilium per errori eBPF
kubectl logs -n kube-system daemonset/cilium | grep -E "ERROR|WARN|bpf"

# Verifica la versione kernel vs requisiti Cilium
uname -r  # deve essere >= 5.4 per Cilium 1.15+
# Per kube-proxy replacement: >= 5.10 raccomandato

# Reset della configurazione BPF (ultima risorsa)
kubectl exec -n kube-system daemonset/cilium -- cilium bpf ct flush global
```

### bpftrace: "No such file or directory" su tracepoints

**Sintomo:** `bpftrace -e 'tracepoint:syscalls:sys_enter_openat {...}'` fallisce con file not found.

```bash
# Verifica se i tracepoints esistono sul kernel corrente
ls /sys/kernel/debug/tracing/events/syscalls/ | grep openat

# Monta debugfs se non montato
mount -t debugfs none /sys/kernel/debug

# Lista tutti i tracepoints disponibili con bpftrace
bpftrace -l 'tracepoint:syscalls:*'
bpftrace -l 'kprobe:tcp_*'

# Verifica le capabilities necessarie (servono root o CAP_BPF)
capsh --print | grep bpf
```

### Alta latenza dopo attach XDP program

**Sintomo:** la latenza di rete aumenta dopo il caricamento di un programma XDP.

**Causa:** programma XDP troppo complesso o con molti accessi a maps — XDP viene eseguito per ogni pacchetto, anche a 10Gbps.

```bash
# Misura le statistiche di esecuzione del programma
bpftool prog show id <PROG_ID>
# Controlla "run_cnt" e "run_time_ns"

# Profila il programma XDP
bpftool prog profile id <PROG_ID> duration 5 cycles instructions

# Se il programma è troppo lento: considera di usare TC invece di XDP
# TC è più lento ma più flessibile e meno critico per la latenza
bpftool net attach tc id <PROG_ID> dev eth0 ingress
```

## Relazioni

??? info "CNI — Cilium usa eBPF per il networking Kubernetes"
    Cilium implementa il CNI Kubernetes usando programmi eBPF a livello XDP e TC per il forwarding dei pacchetti, sostituendo completamente kube-proxy e iptables.

    **Approfondimento →** [CNI — Container Network Interface](../kubernetes/cni.md)

??? info "Runtime Security — Falco e Tetragon usano eBPF"
    Falco usa eBPF per intercettare le syscall dei container e rilevare comportamenti anomali. Tetragon usa BPF LSM per enforcement delle policy direttamente nel kernel.

    **Approfondimento →** [Security Runtime — Seccomp e AppArmor](../../security/runtime/seccomp-apparmor.md)

??? info "Modello OSI — eBPF opera a livello 2-4"
    I programmi XDP operano al livello 2 (data link), i programmi TC ai livelli 3-4. Comprendere il modello OSI aiuta a scegliere il giusto hook point.

    **Approfondimento →** [Modello OSI](modello-osi.md)

## Riferimenti

- [ebpf.io — The eBPF Foundation](https://ebpf.io/)
- [Kernel BPF Documentation](https://www.kernel.org/doc/html/latest/bpf/index.html)
- [libbpf GitHub — libreria C ufficiale](https://github.com/libbpf/libbpf)
- [bpftrace Reference Guide](https://github.com/bpftrace/bpftrace/blob/master/docs/reference_guide.md)
- [BCC Tools Reference](https://github.com/iovisor/bcc/blob/master/docs/reference_guide.md)
- [Cilium eBPF Datapath Documentation](https://docs.cilium.io/en/stable/network/ebpf/)
- [Brendan Gregg — BPF Performance Tools (book)](https://www.brendangregg.com/bpf-performance-tools-book.html)
- [XDP Tutorial (xdp-project)](https://github.com/xdp-project/xdp-tutorial)
- [Learning eBPF — Liz Rice (O'Reilly, free)](https://isovalent.com/learning-ebpf/)
