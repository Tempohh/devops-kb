---
title: "Resource Tuning Multi-Linguaggio in Container"
slug: resource-tuning
category: dev
tags: [performance, golang, dotnet, nodejs, python, kubernetes, cpu, memory, profiling, container]
search_keywords: [resource tuning, cpu tuning container, memory tuning microservizi, GOMAXPROCS, automaxprocs, go kubernetes cpu, golang container cpu, dotnet thread pool, ThreadPool SetMinThreads, dotnet kubernetes, UV_THREADPOOL_SIZE, node.js cluster mode, node cluster kubernetes, gunicorn formula, python worker container, python gunicorn cpu, CPU throttling, CFS bandwidth, cpu period quota, cpu throttle kubernetes, memory overcommit, OOM container, pprof golang, dotnet-trace, async-profiler jvm, profiling in produzione, resource limits microservizi, cpu limits kubernetes, go runtime GOMAXPROCS, dotnet threadpool tuning, nodejs libuv, gunicorn workers, python uwsgi, CFS scheduler linux]
parent: dev/runtime/_index
related: [dev/runtime/jvm-tuning, containers/kubernetes/resource-management]
official_docs: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Resource Tuning Multi-Linguaggio in Container

## Panoramica

Ogni runtime ha le proprie euristiche per determinare quanti thread creare, quante goroutine schedulare, e quanta memoria pre-allocare. In un ambiente bare-metal queste euristiche leggono correttamente l'hardware disponibile; all'interno di un container Kubernetes con `cpu.limits` e `memory.limits`, diversi runtime (o loro versioni meno recenti) dimensionano thread e heap sul nodo sottostante — non sul container — portando a over-provisioning di thread, throttling CPU aggressivo, e OOM kill. Le versioni recenti di Go (≥1.25), .NET e Node.js sono parzialmente *container-aware*: la tabella sotto indica cosa è automatico e cosa resta da configurare. Questo documento descrive il tuning specifico per linguaggio di **Go** (GOMAXPROCS, automaxprocs), **.NET** (ThreadPool sizing), **Node.js** (UV_THREADPOOL_SIZE, cluster mode), e **Python** (Gunicorn worker formula), con una sezione trasversale su **CPU throttling CFS**, **memory overcommit**, e **profiling in produzione** con strumenti nativi per ogni runtime.

| Runtime | CPU limit rispettato di default? | Da configurare comunque |
|---|---|---|
| Go ≥ 1.25 | Sì (GOMAXPROCS da cgroup, aggiornato dinamicamente) | `GOMEMLIMIT` |
| Go < 1.25 | No (usa `NumCPU()` del nodo) | `automaxprocs`, `GOMEMLIMIT` |
| .NET ≥ 3.0 | Sì (`ProcessorCount` = ceil del limit) | Thread pool min, GC heap count/limit |
| Node.js | No per cluster/thread pool | `--max-old-space-size`, `UV_THREADPOOL_SIZE`, n. worker |
| Python (Gunicorn) | No (`cpu_count()` = nodo) | n. worker |

!!! warning "Leggere i limiti del container, non del nodo"
    Il bug più comune: il container vede 32 vCPU del nodo ma ha `cpu.limit: 500m` (0.5 core). Il runtime spawna 32 worker thread — tutti vengono throttled dal kernel CFS perché il budget CPU disponibile è 0.5 core/s ogni secondo. Il risultato è latenza alta e CPU throttle al 90%+, non insufficienza di risorse.

---

## Concetti Chiave

### CFS Bandwidth Control: come Kubernetes throttla la CPU

Il kernel Linux usa il **Completely Fair Scheduler (CFS)** con bandwidth control per applicare i `cpu.limits`. Ogni container riceve un **budget CPU** calcolato come:

```
budget = cpu.limit × cpu.cfs_period_us
```

Per default `cpu.cfs_period_us = 100ms`. Un container con `cpu.limit: 500m` ha un budget di 50ms ogni 100ms — può usare la CPU per 50ms, poi viene **throttled** per i restanti 50ms del periodo.

```bash
# Verificare throttling reale nel container (dentro il pod)
cat /sys/fs/cgroup/cpu/cpu.stat
# Output:
# nr_periods 1234      ← numero di periodi CFS trascorsi
# nr_throttled 567     ← quanti periodi sono stati throttled
# throttled_time 28350000000  ← ns totali in throttle

# Calcolo percentuale throttle:
# throttle% = nr_throttled / nr_periods × 100
# Se > 25% → il container viene throttled significativamente

# Con cgroup v2 (default sulle distro recenti; GA in Kubernetes 1.25):
cat /sys/fs/cgroup/cpu.stat
# stessi campi nr_periods / nr_throttled, ma il tempo è in throttled_usec (µs)
```

```bash
# Metriche Prometheus per CPU throttling (esposte da cAdvisor/kubelet)
# Frazione di periodi CFS throttled per container negli ultimi 5 minuti:
rate(container_cpu_cfs_throttled_periods_total{container="my-service"}[5m])
  / rate(container_cpu_cfs_periods_total{container="my-service"}[5m])

# Alert consigliato: throttle > 25% sostenuto per >5m indica un problema reale
```

!!! note "cpu.request vs cpu.limit e throttling"
    Solo `cpu.limit` causa throttling CFS. `cpu.request` influenza solo lo scheduling (priorità relativa tra pod). Un container senza `cpu.limit` non viene mai throttled dalla CFS — ma può affamare altri pod sullo stesso nodo. In produzione usa sempre entrambi.

### Memory Overcommit e OOM

Il kernel Linux permette l'overcommit di memoria virtuale: un processo può allocare più memoria di quella fisica disponibile, purché non la tocchi effettivamente. I container con `memory.limit` hanno però un tetto rigido: superarlo causa **OOM kill** (`exit code 137`).

| Situazione | Comportamento |
|---|---|
| Allocazione < `memory.limit` | Normale |
| Allocazione > `memory.limit` | SIGKILL immediato (exit code 137) |
| Allocazione > RAM nodo (senza limit) | OOM killer del nodo sceglie vittime |
| `memory.request` = `memory.limit` | QoS Guaranteed — bassa probabilità di OOM kill del nodo |

```bash
# Rilevare OOM kill di un pod
kubectl describe pod <pod> | grep -A3 "Last State"
# OOMKilled con Exit Code 137

# Metriche Prometheus
container_oom_events_total{namespace="production"}

# Dmesg sul nodo (richiede accesso al nodo)
dmesg | grep -E "oom_kill|Out of memory"
```

---

## Go: GOMAXPROCS e automaxprocs

### Il problema

Go usa `GOMAXPROCS` per determinare il numero di thread OS che eseguono goroutine in parallelo. Fino a Go 1.24 il default (dalla Go 1.5) è `runtime.NumCPU()` — che legge il numero di vCPU del **nodo**, non del container.

!!! note "Go 1.25+: GOMAXPROCS container-aware"
    Da Go 1.25 il runtime legge il CPU bandwidth limit del cgroup (v1 e v2) e imposta `GOMAXPROCS = min(NumCPU, limit arrotondato per eccesso)`, **aggiornandolo periodicamente** se il limit cambia (es. in-place resize). Il comportamento si attiva solo se la direttiva `go` in `go.mod` è ≥ 1.25 ed è disattivato se `GOMAXPROCS` è impostato via env var o chiamando `runtime.GOMAXPROCS`. Opt-out: `GODEBUG=containermaxprocs=0,updatemaxprocs=0`. Con Go ≥ 1.25 `automaxprocs` non serve più; resta utile per Go < 1.25. Differenza: `automaxprocs` arrotonda per **difetto** (min 1), il runtime per **eccesso**.

```bash
# In un container con cpu.limit: 500m su nodo da 16 core:
# GOMAXPROCS default = 16
# Budget CPU disponibile = 0.5 core
# 16 thread goroutine si contendono 0.5 core → throttling massiccio
```

### automaxprocs — per Go < 1.25

La libreria `automaxprocs` di Uber (non è parte della stdlib) legge i cgroup del container e imposta automaticamente `GOMAXPROCS` al valore appropriato rispetto al `cpu.limit`:

```go
// main.go — aggiungere all'inizio di main()
import (
    _ "go.uber.org/automaxprocs"  // blank import per side effect
    "log"
)

func main() {
    // automaxprocs imposta GOMAXPROCS automaticamente e logga il valore:
    // "maxprocs: Updating GOMAXPROCS=1: using minimum allowed GOMAXPROCS"
    // (per cpu.limit: 500m → GOMAXPROCS=1)

    // ... resto dell'applicazione
}
```

```bash
# Aggiungere la dipendenza
go get go.uber.org/automaxprocs

# Comportamento con diversi cpu.limit:
# cpu.limit: 250m → GOMAXPROCS=1 (minimo 1)
# cpu.limit: 500m → GOMAXPROCS=1
# cpu.limit: 1000m → GOMAXPROCS=1
# cpu.limit: 2000m → GOMAXPROCS=2
# cpu.limit: 4000m → GOMAXPROCS=4
# Formula: floor(cpu.limit) con minimo 1
```

!!! tip "automaxprocs in container senza limits"
    Se il container non ha `cpu.limit`, automaxprocs usa `runtime.NumCPU()` come fallback — stesso comportamento del default Go. Aggiungere automaxprocs è quindi sempre sicuro, anche in ambienti misti.

### Impostazione manuale GOMAXPROCS

Se non si vuole usare automaxprocs (es. per dipendenze minime), è possibile impostare manualmente:

```yaml
# Kubernetes Deployment — env var GOMAXPROCS
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-go-service
spec:
  template:
    spec:
      containers:
        - name: app
          image: my-go-service:1.0
          env:
            - name: GOMAXPROCS
              valueFrom:
                resourceFieldRef:
                  resource: limits.cpu
                  divisor: "1"  # divide per 1 → valore intero ceil
          resources:
            requests:
              cpu: "500m"
              memory: "128Mi"
            limits:
              cpu: "2000m"
              memory: "256Mi"
```

```go
// Impostazione programmatica (alternativa all'import automatico)
import (
    "os"
    "runtime"
    "strconv"
)

func init() {
    // Leggi GOMAXPROCS da env var, con fallback calcolato
    if v := os.Getenv("GOMAXPROCS"); v != "" {
        if n, err := strconv.Atoi(v); err == nil && n > 0 {
            runtime.GOMAXPROCS(n)
        }
    }
}
```

### GOMEMLIMIT — il GC conosce il limite di memoria

Il GC Go dimensiona l'heap sul solo `GOGC` (default 100: il GC parte quando l'heap raddoppia), senza sapere del `memory.limit`: un picco può superare il limite e causare OOM kill. `GOMEMLIMIT` (Go 1.19+) è un *soft limit* sul totale di memoria del runtime: il GC diventa più aggressivo avvicinandosi al valore, invece di lasciare crescere l'heap.

```yaml
env:
  - name: GOMEMLIMIT
    value: "230MiB"   # ~90% di limits.memory: 256Mi — margine per stack, cgo, buffer non-heap
```

!!! warning "Soft limit"
    Se il live heap supera `GOMEMLIMIT` il GC gira in continuo (death spiral, limitato al ~50% della CPU) e l'app rallenta senza crashare. Dimensiona il limit sul working set reale, non solo sul valore del container.

### Profiling Go in produzione: pprof

Il package `net/http/pprof` espone endpoint HTTP per il profiling live a basso overhead (<5% CPU):

```go
// main.go — abilitare pprof (solo in ambienti controllati)
import _ "net/http/pprof"
import "net/http"

func main() {
    // Esporre su porta separata (NON sulla porta pubblica del servizio)
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()
    // ... resto dell'app
}
```

```bash
# Raccogliere CPU profile per 30 secondi (via kubectl port-forward)
kubectl port-forward pod/<pod-name> 6060:6060 &

# CPU profile → flamegraph
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30
# In pprof shell: web (call graph SVG nel browser); per il flamegraph usa -http=:8080 (vedi sotto)

# Heap profile (oggetti allocati)
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine dump (verifica goroutine leak)
curl http://localhost:6060/debug/pprof/goroutine?debug=1 | head -50

# Scaricare e analizzare con pprof tool
curl -o cpu.prof http://localhost:6060/debug/pprof/profile?seconds=30
go tool pprof -http=:8080 cpu.prof
```

```bash
# Raccolta non-interattiva per CI/produzione
go tool pprof -pdf -output=/tmp/cpu.pdf http://localhost:6060/debug/pprof/profile?seconds=30
# Copiare fuori dal container
kubectl cp <ns>/<pod>:/tmp/cpu.pdf ./cpu.pdf
```

---

## .NET: Thread Pool Sizing

### Il problema

Il .NET Thread Pool usa due euristiche per dimensionarsi: il numero di core (per i worker thread) e la disponibilità di I/O (per gli I/O completion thread). Dal .NET Core 3.0 `Environment.ProcessorCount` rispetta il `cpu.limit` del container (arrotondato per eccesso, es. `500m` → 1), quindi pool e GC partono già dimensionati sul limit. Il problema residuo è un altro: il pool parte con `MinThreads = ProcessorCount` e, davanti a un burst di lavoro bloccante o async mal scritto, aggiunge thread con l'algoritmo *hill-climbing* (circa 1–2 al secondo) — su limit bassi ne risultano spike di latenza dopo un burst.

### ThreadPool.SetMinThreads e SetMaxThreads

```csharp
// Program.cs o Startup.cs — configurare il thread pool all'avvio
using System.Threading;

// ProcessorCount rispetta già il cpu.limit del container (ceil);
// per forzare un valore: env DOTNET_PROCESSOR_COUNT
int cpuLimit = Environment.ProcessorCount;

// Worker threads: suggerita = cpuLimit * 2 (per workload I/O bound)
// Per workload CPU-bound: uguale a cpuLimit
int workerThreads = Math.Max(cpuLimit * 2, 4);
int completionPortThreads = Math.Max(cpuLimit, 2);

ThreadPool.SetMinThreads(workerThreads, completionPortThreads);
ThreadPool.SetMaxThreads(workerThreads * 4, completionPortThreads * 4);

// Log del thread pool corrente
ThreadPool.GetMinThreads(out int minWorker, out int minCompletion);
ThreadPool.GetMaxThreads(out int maxWorker, out int maxCompletion);
Console.WriteLine($"ThreadPool: min={minWorker}/{minCompletion}, max={maxWorker}/{maxCompletion}");
```

### Variabili d'ambiente .NET container-relevant

```yaml
# Kubernetes Deployment — variabili d'ambiente .NET
# ATTENZIONE: le env var DOTNET_GC* sono interpretate come valori ESADECIMALI
env:
  # Cap esplicito dei heap GC (Server GC: 1 heap per core). "2" = 2 heap
  - name: DOTNET_GCHeapCount
    value: "2"

  # Hard limit heap come percentuale della memory.limit. 0x4B = 75
  # (con memory.limit presente il default del runtime è già 75%)
  - name: DOTNET_GCHeapHardLimitPercent
    value: "4B"

  # Riduce il footprint a scapito del throughput (scala 0-9)
  - name: DOTNET_GCConserveMemory
    value: "5"

  # Workstation GC invece di Server GC: meno memoria, adatto a pod con ~1 CPU
  - name: DOTNET_gcServer
    value: "0"

resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
  limits:
    cpu: "2000m"
    memory: "512Mi"
```

```bash
# Verificare la configurazione thread pool a runtime
# Via dotnet-counters (dentro il container)
dotnet-counters monitor --process-id 1 \
  System.Runtime[threadpool-thread-count,threadpool-queue-length,threadpool-completed-items-count]

# Output live:
# [System.Runtime]
#   ThreadPool Thread Count                       8
#   ThreadPool Queue Length                       0
#   ThreadPool Completed Items Count / sec    12345
```

### Profiling .NET in produzione: dotnet-trace e dotnet-dump

```bash
# 1. Installare tools di diagnostica nel container (o nell'immagine base)
dotnet tool install --global dotnet-trace
dotnet tool install --global dotnet-dump
dotnet tool install --global dotnet-counters

# 2. CPU trace per 30 secondi
dotnet-trace collect --process-id 1 --duration 00:00:30 \
  --output /tmp/trace.nettrace

# 3. Copiare fuori e analizzare con PerfView o VS
kubectl cp <ns>/<pod>:/tmp/trace.nettrace ./trace.nettrace
# Aprire con PerfView (Windows) o VS 2022 → Diagnostics → .NET Trace

# 4. Memory dump per analisi OOM
dotnet-dump collect --process-id 1 --output /tmp/dump.dmp
kubectl cp <ns>/<pod>:/tmp/dump.dmp ./dump.dmp
dotnet-dump analyze /tmp/dump.dmp
# In shell dump: dumpheap -stat (oggetti per tipo con size)
```

```bash
# Alternativa: esportare metriche runtime verso Prometheus
# (OpenTelemetry .NET SDK + OpenTelemetry.Instrumentation.Runtime)
dotnet add package OpenTelemetry.Instrumentation.Runtime
dotnet add package OpenTelemetry.Exporter.Prometheus.AspNetCore
# Espone thread pool (thread count, queue length), GC collections e heap size;
# i nomi esatti delle metriche dipendono dalla versione del pacchetto
```

!!! tip "Server GC vs Workstation GC in container"
    Server GC crea un heap (e un thread GC dedicato) per core: più throughput, più memoria. Il numero di heap segue il `ProcessorCount` visto dal runtime, quindi il cpu.limit; con `cpu.limit` ≤ 1 o memoria stretta Workstation GC è di solito la scelta migliore. Se usi Server GC, `DOTNET_GCHeapCount` (esadecimale) mette un tetto esplicito.

---

## Node.js: UV_THREADPOOL_SIZE e Cluster Mode

### Il problema

Node.js è single-threaded per il JavaScript, ma usa un **thread pool libuv** per operazioni I/O asincrone (fs, crypto, DNS). Il default è 4 thread indipendentemente dal numero di core. Per sfruttare più CPU, Node.js usa il **cluster module** che spawna N worker process (fork). Senza tuning, un singolo processo Node.js usa al massimo 1 vCPU per il JS event loop.

### UV_THREADPOOL_SIZE

```bash
# UV_THREADPOOL_SIZE controlla il thread pool libuv
# Default: 4 thread — adatto per la maggior parte dei casi
# Aumentare per: operazioni crypto intensive (TLS, bcrypt), fs intensive

# Kubernetes env var
env:
  - name: UV_THREADPOOL_SIZE
    value: "8"  # Regola: min(cpu.limit * 2, 1024) per workload I/O
```

```javascript
// Verifica del thread pool size a runtime
const os = require('os');
console.log('CPU count:', os.cpus().length);
console.log('UV_THREADPOOL_SIZE:', process.env.UV_THREADPOOL_SIZE || 4);

// Attenzione: UV_THREADPOOL_SIZE va impostato PRIMA di richiedere
// qualsiasi modulo che usa libuv (node:crypto, node:fs con callback sync)
// Impostarlo via env var è il modo corretto
```

```bash
# Test bcrypt throughput con diversi UV_THREADPOOL_SIZE
# (operazione che usa il thread pool libuv)
node -e "
const bcrypt = require('bcrypt');
const start = Date.now();
const promises = Array(10).fill().map(() => bcrypt.hash('test', 10));
Promise.all(promises).then(() => console.log(Date.now() - start, 'ms'));
"
# Ordine di grandezza atteso (dipende da hardware e cost factor): con 4 thread
# 10 hash richiedono ~3 "ondate"; con 8+ thread (e CPU sufficiente) ~2.
# Oltre il numero di core disponibili NON c'è guadagno: i thread vengono throttled.
```

### Cluster Mode in Kubernetes

```javascript
// cluster.js — pattern per sfruttare tutti i CPU limit
const cluster = require('cluster');
const os = require('os');

if (cluster.isPrimary) {
    // Numero di worker = cpu.limit (letto da cgroup o env var)
    const cpuLimit = parseInt(process.env.CPU_LIMIT) || os.availableParallelism();
    const numWorkers = Math.max(cpuLimit, 1);

    console.log(`Primary ${process.pid} — spawning ${numWorkers} workers`);

    for (let i = 0; i < numWorkers; i++) {
        cluster.fork();
    }

    cluster.on('exit', (worker, code, signal) => {
        console.log(`Worker ${worker.process.pid} died (${signal || code}), restarting...`);
        cluster.fork(); // restart automatico
    });
} else {
    // Worker: avviare il server HTTP qui
    require('./server');
    console.log(`Worker ${process.pid} started`);
}
```

```yaml
# Kubernetes Deployment — Node.js con cluster mode
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-node-service
spec:
  template:
    spec:
      containers:
        - name: app
          image: my-node-service:1.0
          env:
            - name: UV_THREADPOOL_SIZE
              value: "8"
            - name: NODE_OPTIONS
              value: "--max-old-space-size=384"  # 384 MB heap V8 (per container 512Mi)
            - name: CPU_LIMIT
              valueFrom:
                resourceFieldRef:
                  resource: limits.cpu
                  divisor: "1"
          resources:
            requests:
              cpu: "500m"
              memory: "256Mi"
            limits:
              cpu: "2000m"
              memory: "512Mi"
```

!!! warning "Cluster mode e statefulness"
    Ogni worker è un processo separato con memoria separata. Cache in-process (Map, WeakMap, variabili globali) non è condivisa tra worker. Per state condiviso usare Redis. Questo vale anche per WebSocket — usare sticky sessions o un broker esterno.

### NODE_OPTIONS: --max-old-space-size

Il default dell'heap V8 dipende dalla memoria rilevata e dalla versione di Node.js; nelle versioni recenti il limite del cgroup viene considerato, ma il valore risultante può comunque essere troppo vicino (o oltre) al `memory.limit` perché V8 non conta buffer nativi, stack e memoria fuori heap. Impostarlo esplicitamente rende il comportamento prevedibile: il GC lavora di più *prima* del limite invece di farti raggiungere l'OOM kill.

```bash
# Calcolo consigliato: ~70-75% di memory.limit in MB
# Container con memory.limit: 512Mi → --max-old-space-size=384
# Container con memory.limit: 1Gi  → --max-old-space-size=768
# Container con memory.limit: 2Gi  → --max-old-space-size=1536

# Via env var (più flessibile nei Deployment K8s):
NODE_OPTIONS="--max-old-space-size=384"

# In PM2 (alternativa a cluster nativo):
# ecosystem.config.js
module.exports = {
  apps: [{
    name: 'my-service',
    script: './server.js',
    instances: process.env.CPU_LIMIT || 'max',
    node_args: '--max-old-space-size=384',
    exec_mode: 'cluster'
  }]
};
```

---

## Python: Gunicorn Worker Formula

### Il problema

Python (con CPython) ha il **GIL (Global Interpreter Lock)** che impedisce l'esecuzione parallela di bytecode Python in un singolo processo. Per sfruttare più CPU, è necessario usare **processi multipli** (multi-process, non multi-thread). Gunicorn gestisce questo con il suo worker model.

### Formula worker Gunicorn

```bash
# Formula suggerita dalla documentazione Gunicorn (punto di partenza, worker sync):
# workers = (2 × cpu_count) + 1
# Perché: mentre un worker sync è bloccato su I/O, gli altri usano la CPU

# Per container Kubernetes, leggere cpu.limit:
if [ -r /sys/fs/cgroup/cpu.max ]; then            # cgroup v2: "quota period" oppure "max period"
  CPU_LIMIT=$(awk '$1=="max"{print 0; next} {print int($1/$2)}' /sys/fs/cgroup/cpu.max)
else                                               # cgroup v1: quota = -1 se illimitato
  CPU_LIMIT=$(awk '{print ($1>0)? int($1/100000) : 0}' /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null)
fi
# Senza limit (0 o vuoto) o limit < 1 CPU → minimo 1 (nproc vedrebbe i core del nodo)
[ "${CPU_LIMIT:-0}" -lt 1 ] && CPU_LIMIT=1
WORKERS=$((2 * CPU_LIMIT + 1))

# Esempio con cpu.limit: 2000m → CPU_LIMIT=2 → WORKERS=5
# Esempio con cpu.limit: 500m  → CPU_LIMIT=0 → CPU_LIMIT=1 → WORKERS=3

gunicorn --workers $WORKERS --bind 0.0.0.0:8000 myapp:app
```

```python
# Configurazione Gunicorn completa per container (gunicorn.conf.py)
import multiprocessing
import os

# Lettura cpu limit da cgroup
def get_cpu_limit():
    try:
        # cgroup v2
        with open('/sys/fs/cgroup/cpu.max') as f:
            content = f.read().strip()
            quota, period = content.split()
            if quota != 'max':
                return max(int(int(quota) / int(period)), 1)
    except Exception:
        pass
    try:
        # cgroup v1
        with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us') as f:
            quota = int(f.read().strip())
        with open('/sys/fs/cgroup/cpu/cpu.cfs_period_us') as f:
            period = int(f.read().strip())
        if quota > 0:
            return max(int(quota / period), 1)
    except Exception:
        pass
    return multiprocessing.cpu_count()

cpu_count = get_cpu_limit()

# Gunicorn settings
bind = "0.0.0.0:8000"
workers = int(os.getenv("GUNICORN_WORKERS", (2 * cpu_count) + 1))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")  # sync, gevent, uvicorn_worker.UvicornWorker
worker_tmp_dir = "/dev/shm"  # heartbeat in RAM: evita worker 'bloccati' se /tmp del container è lento (overlayfs)
worker_connections = 1000   # per worker async (gevent/asyncio)
timeout = 120
keepalive = 5
preload_app = True          # carica l'app nel master → fork copy-on-write

# Logging
accesslog = "-"             # stdout
errorlog = "-"              # stderr
loglevel = "info"
```

```yaml
# Kubernetes Deployment — Python/Gunicorn
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-python-service
spec:
  template:
    spec:
      containers:
        - name: app
          image: my-python-service:1.0
          command: ["gunicorn", "--config", "/app/gunicorn.conf.py", "myapp:app"]
          env:
            - name: GUNICORN_WORKERS
              value: "5"  # Override manuale (es. 2 CPU → 5 workers)
            - name: GUNICORN_WORKER_CLASS
              value: "uvicorn_worker.UvicornWorker"  # per FastAPI/ASGI (pacchetto uvicorn-worker)
          resources:
            requests:
              cpu: "500m"
              memory: "256Mi"
            limits:
              cpu: "2000m"
              memory: "512Mi"
```

### Worker class: sync vs async

| Worker class | Quando usare | Package |
|---|---|---|
| `sync` (default) | Workload CPU-bound, Django tradizionale | nessuno |
| `gevent` | Molte connessioni I/O-bound simultanee | `gevent` |
| `uvicorn_worker.UvicornWorker` | FastAPI, Starlette (ASGI) | `uvicorn-worker` (il vecchio `uvicorn.workers` è deprecato) |
| `tornado` | Applicazioni Tornado | `tornado` |

```bash
# Installare il worker class scelto
pip install gunicorn gevent            # per worker gevent
pip install gunicorn uvicorn-worker   # per FastAPI/ASGI
```

!!! tip "preload_app = True — risparmio memoria"
    Con `preload_app`, il master carica l'app Python in memoria, poi i worker vengono creati con `fork()`. Il kernel usa **copy-on-write** — le pagine di codice Python non modificate sono condivise tra master e worker. Con 5 worker, il risparmio può essere 50-200 MB rispetto al caricamento individuale.

### Profiling Python in produzione: py-spy

```bash
# py-spy: profiler sampling per Python a basso overhead (<1% CPU)
pip install py-spy

# CPU profile per 30 secondi (flamegraph SVG)
py-spy record -d 30 -f flamegraph -o /tmp/profile.svg --pid $(pgrep -f gunicorn | head -1)

# Top-like interattivo (senza salvare file)
py-spy top --pid $(pgrep -f gunicorn | head -1)

# Subprocess di Gunicorn: profilare un worker specifico
ps aux | grep gunicorn
py-spy record -d 30 -o /tmp/worker.svg --pid <worker-pid>

# Copiare fuori dal container
kubectl cp <ns>/<pod>:/tmp/profile.svg ./profile.svg
```

```bash
# Alternativa: cProfile per profiling deterministico (overhead alto)
# Usare solo in staging, non in produzione
python -m cProfile -o /tmp/profile.stats myapp.py

# Analisi
python -c "
import pstats
p = pstats.Stats('/tmp/profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)  # top 20 funzioni per tempo cumulativo
"
```

---

## Best Practices

**Go:**
- Usa sempre `automaxprocs` — zero overhead, prevenzione throttling automatica.
- Esponi `pprof` su una porta interna dedicata (es. `:6060`) e proteggi con NetworkPolicy.
- Monitora goroutine count via pprof `/debug/pprof/goroutine` — goroutine leak è la causa più comune di memory leak in Go.

**\.NET:**
- Verifica `Environment.ProcessorCount` a runtime: è la base di pool e GC. Con Server GC, valuta `DOTNET_GCHeapCount` per un tetto esplicito; ricorda che le env `DOTNET_GC*` sono esadecimali.
- Usa `ThreadPool.SetMinThreads` per evitare il "thread pool hill-climbing" (latenza spike nei primi secondi dopo un burst di traffico).
- Con ASP.NET Core, preferire async/await ovunque — riduce la pressione sul thread pool.

**Node.js:**
- Imposta sempre `--max-old-space-size` proporzionale al `memory.limit` del container.
- Usa cluster mode (o PM2) per container con `cpu.limit` > 1 core.
- Non aumentare `UV_THREADPOOL_SIZE` > 1024 (limite libuv; era 128 nelle versioni vecchie) — in pratica resta su valori piccoli: ogni thread costa memoria e contesa CPU.
- In Kubernetes valuta più repliche single-process invece del cluster mode: scaling, isolamento OOM e metriche per-pod sono più semplici.

**Python:**
- Usa la formula `2*CPU+1` come punto di partenza, poi aumenta se il profiling mostra worker idle.
- Con worker gevent o uvicorn, il numero di worker può essere ridotto (es. `CPU`, o 1 per pod con scaling orizzontale) perché ogni worker gestisce molte connessioni concorrenti.
- Evita import a livello di modulo che allocano strutture dati grandi — con `preload_app=True` vengono allocate nel master e replicate (copy-on-write) in ogni worker.

!!! warning "Vertical pod autoscaling e GOMAXPROCS/workers"
    Se usi VPA (Vertical Pod Autoscaler), i `cpu.limits` possono cambiare dinamicamente. Configurazioni hardcoded di GOMAXPROCS, worker count, o thread pool non si adatteranno. Le env var `resourceFieldRef` sono risolte all'avvio del container e **non** si aggiornano con un resize (anche in-place): servono un restart o una lettura periodica dei cgroup. Go ≥ 1.25 aggiorna GOMAXPROCS da solo; per gli altri runtime verifica il comportamento dopo il resize.

---

## Troubleshooting

### Scenario 1 — CPU throttling alto (>50%) con servizio lento

**Sintomo:** La metrica `container_cpu_cfs_throttled_seconds_total` è alta. Il servizio ha latenze alte ma `kubectl top pod` mostra CPU usage < limit.

**Causa:** Il runtime spawna più thread/process del budget CPU disponibile. Nei periodi di burst, tutti i thread sono attivi contemporaneamente e consumano il budget CFS più velocemente del periodo (100ms), causando throttling per la parte rimanente.

**Soluzione:**

```bash
# 1. Verificare quanti thread sta usando il processo
kubectl exec -it <pod> -- cat /proc/1/status | grep Threads
# Se Threads >> cpu.limit × 4 → over-provisioned

# 2. Per Go — verificare GOMAXPROCS
# Il valore effettivo si vede solo dal processo: logga runtime.GOMAXPROCS(0) all'avvio
# (automaxprocs lo logga già da solo). Intanto confronta i thread con il limit:
kubectl exec -it <pod> -- grep -E 'Threads' /proc/1/status

# 3. Aumentare cpu.limit (se il carico è legittimo)
kubectl set resources deployment/<name> --limits=cpu=2000m

# 4. Ridurre il numero di thread/worker al cpu.limit
# Per Go: aggiungere automaxprocs
# Per Node.js: ridurre cluster workers
# Per Python: ridurre GUNICORN_WORKERS
# Per .NET: ridurre ThreadPool max threads
```

### Scenario 2 — OOM kill con memoria apparentemente sufficiente

**Sintomo:** Il pod viene OOM killed (`exit code 137`) ma `kubectl top pod` mostrava memoria < limit.

**Causa:** `kubectl top` mostra il *working set* (usage meno file cache inattiva), campionato a intervalli: un picco breve tra due campioni non si vede. Inoltre il `memory.limit` del cgroup conta la memoria di tutti i processi (worker Gunicorn, cluster Node.js), page cache attiva e memoria kernel del container.

**Soluzione:**

```bash
# 1. Verificare memoria reale del container (inclusi tutti i processi)
kubectl exec -it <pod> -- cat /sys/fs/cgroup/memory/memory.usage_in_bytes
# oppure cgroup v2:
kubectl exec -it <pod> -- cat /sys/fs/cgroup/memory.current

# 2. Confrontare con il limit
kubectl exec -it <pod> -- cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# 3. Vedere tutti i processi con memoria
kubectl exec -it <pod> -- ps aux --sort=-%mem | head -20

# 4. Per Gunicorn: ridurre workers o aumentare memory.limit
# Ogni worker Python consuma 30-80 MB → 5 workers = 150-400 MB solo di worker

# 5. Per Node.js: ridurre --max-old-space-size
# V8 può usare fino a max-old-space-size × 1.5 incluso GC overhead
```

### Scenario 3 — Avvio lento con molti worker

**Sintomo:** Il pod impiega 30-60s prima che la readiness probe passi. Succede soprattutto dopo un rolling update o un scale-up.

**Causa:** Tutti i worker Gunicorn/cluster Node.js si avviano in parallelo, causando un burst di CPU e I/O che supera il budget CFS → throttling durante l'avvio.

**Soluzione:**

```bash
# 1. Gunicorn: usare --preload (carica l'app nel master, fork è veloce)
gunicorn --preload --workers 5 myapp:app

# 2. Node.js: aggiungere delay progressivo tra fork dei worker
# (in cluster.js)
for (let i = 0; i < numWorkers; i++) {
    setTimeout(() => cluster.fork(), i * 500); // 500ms tra ogni worker
}

# 3. Aumentare initialDelaySeconds nella readiness probe
readinessProbe:
  initialDelaySeconds: 20
  periodSeconds: 5
  failureThreshold: 12

# 4. Usare startupProbe (Kubernetes 1.18+) invece di initialDelaySeconds
startupProbe:
  httpGet:
    path: /health
    port: 8000
  failureThreshold: 30
  periodSeconds: 3  # 30 × 3s = 90s massimo per lo startup
```

### Scenario 4 — Goroutine leak (Go): memoria cresce indefinitamente

**Sintomo:** Il consumo di memoria del Pod cresce lentamente ma inesorabilmente. Non c'è OOM ma il pod viene riavviato per memory eviction o supera il limit dopo ore/giorni.

**Causa:** Goroutine che non terminano (goroutine leak) — ogni goroutine usa 2-8 KB di stack. Con migliaia di goroutine leakate, l'overhead diventa significativo.

**Soluzione:**

```bash
# 1. Verificare goroutine count nel tempo
curl http://localhost:6060/debug/pprof/goroutine?debug=1 | grep "^goroutine" | wc -l

# Monitorare nel tempo (se in crescita continua → leak)
watch -n 30 'curl -s http://localhost:6060/debug/pprof/goroutine?debug=1 | grep "^goroutine" | wc -l'

# 2. Analisi dettagliata — dove sono le goroutine bloccate
curl http://localhost:6060/debug/pprof/goroutine?debug=2 | head -200

# 3. Flamegraph goroutine
go tool pprof -http=:8080 http://localhost:6060/debug/pprof/goroutine

# Pattern comuni di goroutine leak:
# - goroutine bloccata su channel send/receive senza select con context
# - goroutine in http.Get senza timeout
# - ticker non stoppato (ticker.Stop() non chiamato)
# Fix: usare sempre context con timeout/cancel per operazioni async
```

---

## Relazioni

??? info "JVM Tuning per Kubernetes — Runtime Java"
    Il tuning JVM (GOMAXPROCS equivalente JVM, heap sizing, GC) è trattato in dettaglio nel documento dedicato. Le strategie di CFS throttling e OOM prevention descritte qui si applicano ugualmente ai container JVM.

    **Approfondimento completo →** [JVM Tuning per Kubernetes](jvm-tuning.md)

??? info "Kubernetes Resource Management — Limits e Requests"
    Le configurazioni di `cpu.requests`, `cpu.limits`, `memory.requests`, `memory.limits`, QoS class e VPA che influenzano il comportamento dei runtime sono documentate in Resource Management.

    **Approfondimento completo →** [Kubernetes Resource Management](../../containers/kubernetes/resource-management.md)

---

## Riferimenti

- [Uber automaxprocs — GitHub](https://github.com/uber-go/automaxprocs)
- [Go runtime package — GOMAXPROCS](https://pkg.go.dev/runtime#GOMAXPROCS)
- [.NET ThreadPool documentation](https://learn.microsoft.com/en-us/dotnet/api/system.threading.threadpool)
- [.NET container environment variables](https://learn.microsoft.com/en-us/dotnet/core/runtime-config/)
- [Node.js cluster module](https://nodejs.org/api/cluster.html)
- [libuv thread pool — UV_THREADPOOL_SIZE](http://docs.libuv.org/en/v1.x/threadpool.html)
- [Gunicorn configuration](https://docs.gunicorn.org/en/stable/configure.html)
- [py-spy — sampling profiler for Python](https://github.com/benfred/py-spy)
- [Linux CFS Bandwidth Control](https://www.kernel.org/doc/html/latest/scheduler/sched-bwc.html)
- [Kubernetes CPU requests vs limits](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
