---
title: "JVM Tuning per Kubernetes"
slug: jvm-tuning
category: dev
tags: [jvm, java, kubernetes, performance, gc, heap, profiling, graalvm]
search_keywords: [jvm tuning, jvm kubernetes, heap sizing, garbage collector, G1GC, ZGC, Shenandoah, MaxRAMPercentage, Xmx kubernetes, container-aware jvm, metaspace, code cache, ReservedCodeCacheSize, async-profiler, JFR, Java Flight Recorder, Mission Control, OOMKiller exit code 137, OOM kill pod, java in container, jvm container, java 17 kubernetes, java 21 kubernetes, virtual threads jvm, jvm vs graalvm native, graalvm native image, startup time java, heap dump, jvm flags, jvm options, java microservizi, spring boot jvm, quarkus jvm, jvm heap formula, jvm profiling, jvm monitoring, jvm metaspace, jvm codecache, compact heap, virtual threads loom, jvm 21, java container memory, kubernetes memory limit jvm, java resource limits]
parent: dev/runtime/_index
related: [dev/linguaggi/java-spring-boot, dev/linguaggi/java-quarkus, containers/kubernetes/resource-management]
official_docs: https://docs.oracle.com/en/java/javase/21/gctuning/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# JVM Tuning per Kubernetes

## Panoramica

La JVM (Java Virtual Machine) non era originariamente progettata per girare dentro container con limiti di memoria rigidi: le versioni pre-Java 10 leggevano la RAM dell'host ignorando i cgroup, causando heap allocation sbagliate e OOM kill silenziosi. Da **Java 11+** la JVM è pienamente **container-aware**: usa automaticamente i cgroup per determinare la memoria disponibile e calcola l'heap di default come 25% della RAM del container. Il tuning JVM in Kubernetes richiede di gestire quattro aree: (1) **heap sizing** corretto rispetto ai `limits` K8s, (2) **scelta del Garbage Collector** in base ai requisiti di latenza, (3) **gestione della memoria non-heap** (Metaspace, Code Cache, thread stack), (4) **profiling e diagnostica** per identificare colli di bottiglia senza interrompere il servizio. Queste configurazioni si applicano a qualsiasi workload JVM: Spring Boot, Quarkus in modalità JVM, Micronaut, Jakarta EE.

!!! warning "Java < 11 in container"
    Se usi ancora Java 8 o 10, la JVM legge la RAM dell'host, non quella del container. Su un nodo da 64 GB, la JVM si alloca un heap da ~16 GB anche se il Pod ha limit di 512 MB → OOM kill immediato. Migra a Java 17+ o usa `-XX:+UseContainerSupport` (backportato in Java 8u191+).

---

## Concetti Chiave

### Container-Awareness: come la JVM legge i limiti K8s

Da Java 11, il flag `-XX:+UseContainerSupport` è **attivo per default**. La JVM interroga i cgroup v1/v2 del container per determinare:

| Parametro JVM | Fonte dati | Default |
|---|---|---|
| Memoria massima heap | `memory.limit_in_bytes` (cgroup) | 25% della RAM container |
| CPU disponibili | `cpu.cfs_quota_us / cpu.cfs_period_us` | Numero vCPU visibili nel container |
| GC thread count | CPU disponibili | Proporzionale ai core |

La **formula di default** (25%) è troppo conservativa per la maggior parte dei microservizi. Il tuning corretto prevede di alzarla al 50-75% a seconda del profilo dell'applicazione.

### Memoria JVM: le 4 regioni

```
┌─────────────────────────────────────────────────────────┐
│                   Container Memory Limit                 │
│                        (es. 1 GiB)                       │
├──────────────────────┬──────────────────────────────────┤
│   Java Heap          │   Off-Heap                        │
│   (50-75% del limit) │                                   │
│                      │  ┌─────────────────────────────┐ │
│   Young Gen          │  │ Metaspace (classi JVM)       │ │
│   ├── Eden           │  │ Code Cache (JIT compiled)   │ │
│   └── Survivor       │  │ Thread stacks (~1 MB/thread)│ │
│   Old Gen            │  │ Direct Buffers (NIO)        │ │
│                      │  │ JVM overhead (~50-100 MB)   │ │
└──────────────────────┴──┴─────────────────────────────┘─┘
```

!!! warning "Off-heap invisibile ai limiti heap"
    `-Xmx` controlla solo il **Java Heap**. Metaspace, Code Cache e thread stack crescono indipendentemente. Un container da 1 GiB con `-Xmx900m` può comunque andare in OOM se Metaspace cresce oltre i 100 MB rimanenti. Pianifica sempre 200-300 MB di headroom per l'off-heap.

### Heap Sizing: la formula per microservizi

```
Heap Max = (Container Memory Limit × 0.65) - 50 MB
```

La formula alloca il 65% della RAM al heap e tiene 35% + 50 MB di buffer per off-heap. Per un container da 1 GiB:

```
Heap = (1024 MB × 0.65) - 50 MB = ~615 MB
```

Equivalente JVM flag: `-XX:MaxRAMPercentage=65.0`

**Linee guida per percentuale:**

| Profilo applicazione | MaxRAMPercentage consigliato |
|---|---|
| Microservizio stateless, pochi thread | 70-75% |
| Servizio con I/O intenso, molti thread | 55-65% |
| Servizio con cache in-process (Caffeine, EHCache) | 60-70% (la cache è heap) |
| Servizio con NIO / Netty / gRPC intensivo | 50-60% (molti direct buffers off-heap) |
| Servizio con molte classi dinamiche (Groovy, reflection) | 60-65% (Metaspace più grande) |

---

## Garbage Collector: Scelta e Configurazione

### Panoramica GC disponibili

| GC | Flag | Java Min | Latenza | Throughput | Use case |
|---|---|---|---|---|---|
| **G1GC** | `-XX:+UseG1GC` | 9 (default da 9) | ~10-50ms pause | Alto | Default per la maggior parte dei microservizi |
| **ZGC** | `-XX:+UseZGC` | 15 (prod), 21 (LTS) | <1ms (sub-ms) | Leggermente inferiore | Servizi latency-sensitive, heap >4 GB |
| **Shenandoah** | `-XX:+UseShenandoahGC` | 12 (OpenJDK/Red Hat) | <5ms | Medio | Alternative a ZGC su Red Hat/OpenShift |
| **Serial GC** | `-XX:+UseSerialGC` | tutti | Alte pause | Basso | Container con <256 MB heap, CLI tools |
| **Parallel GC** | `-XX:+UseParallelGC` | tutti | Alte pause | Massimo | Batch, processi offline |

### G1GC — Configurazione Production

G1GC è il collector di default da Java 9 e la scelta corretta per la maggior parte dei microservizi Spring Boot/Quarkus. Bilancia throughput e latenza con pause tipicamente <50ms.

```bash
# Configurazione G1GC per microservizio Spring Boot (container 1 GiB)
JAVA_OPTS="-XX:+UseG1GC \
  -XX:MaxRAMPercentage=65.0 \
  -XX:InitialRAMPercentage=50.0 \
  -XX:MaxGCPauseMillis=200 \
  -XX:G1HeapRegionSize=4m \
  -XX:+G1UseAdaptiveIHOP \
  -XX:InitiatingHeapOccupancyPercent=45 \
  -Xss512k \
  -XX:MetaspaceSize=128m \
  -XX:MaxMetaspaceSize=256m \
  -XX:ReservedCodeCacheSize=128m \
  -XX:+UseStringDeduplication"
```

```yaml
# Deployment Kubernetes con JAVA_OPTS
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  template:
    spec:
      containers:
        - name: app
          image: my-service:1.0
          env:
            - name: JAVA_OPTS
              value: >-
                -XX:+UseG1GC
                -XX:MaxRAMPercentage=65.0
                -XX:InitialRAMPercentage=50.0
                -XX:MaxGCPauseMillis=200
                -XX:MetaspaceSize=128m
                -XX:MaxMetaspaceSize=256m
                -XX:ReservedCodeCacheSize=128m
          resources:
            requests:
              memory: "768Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
```

!!! tip "G1HeapRegionSize"
    G1GC divide l'heap in regioni. La dimensione ideale è: `heap / 2048` regioni. Con heap da 600 MB → 300 KB (usa il default). Con heap da 4 GB → 2 MB. Con heap da 8 GB → 4 MB. Impostare manualmente `-XX:G1HeapRegionSize` solo con heap >4 GB.

### ZGC — Configurazione per Latenza Sub-ms (Java 21)

ZGC è il collector ottimale per servizi con SLA di latenza stretti (<10ms p99). Da Java 21 LTS è pienamente maturo e generazionale (Generational ZGC).

```bash
# ZGC per servizio latency-sensitive (container 2 GiB, Java 21)
JAVA_OPTS="-XX:+UseZGC \
  -XX:+ZGenerational \
  -XX:MaxRAMPercentage=60.0 \
  -XX:InitialRAMPercentage=40.0 \
  -XX:ZAllocationSpikeTolerance=2.0 \
  -XX:ConcGCThreads=2 \
  -Xss512k \
  -XX:MetaspaceSize=128m \
  -XX:MaxMetaspaceSize=256m \
  -XX:ReservedCodeCacheSize=256m"
```

```bash
# Verifica che ZGC sia attivo e controlla pause times
# Output nei log JVM con -Xlog:gc*:stdout:time,uptime,level,tags
-Xlog:gc*:stdout:time,uptime,level,tags:filecount=3,filesize=10m
```

!!! note "ZGC e CPU overhead"
    ZGC esegue il GC in modo concorrente (mentre l'applicazione gira), richiedendo più CPU rispetto a G1GC. Su container con `cpu.limit` basso (<500m), ZGC può essere più lento di G1GC perché i thread GC vengono throttled. Testa sempre con load test prima di scegliere.

### Shenandoah — Red Hat / OpenShift

Shenandoah è sviluppato da Red Hat e incluso nelle distribuzioni OpenJDK di Red Hat. Simile a ZGC per caratteristiche di latenza, ma con un modello di pause leggermente diverso.

```bash
# Shenandoah (solo OpenJDK Red Hat / Adoptium con supporto)
JAVA_OPTS="-XX:+UseShenandoahGC \
  -XX:ShenandoahGCMode=adaptive \
  -XX:MaxRAMPercentage=65.0 \
  -XX:MetaspaceSize=128m \
  -XX:MaxMetaspaceSize=256m"
```

---

## Configurazione & Pratica

### Configurazione Completa Production-Ready

Questo blocco rappresenta la configurazione JVM completa per un microservizio Spring Boot su container da 1 GiB, ottimizzata per un ambiente Kubernetes production:

```bash
# Dockerfile: ENV per Spring Boot
ENV JAVA_OPTS="\
  -XX:+UseG1GC \
  -XX:MaxRAMPercentage=65.0 \
  -XX:InitialRAMPercentage=50.0 \
  -XX:MaxGCPauseMillis=200 \
  -Xss512k \
  -XX:MetaspaceSize=128m \
  -XX:MaxMetaspaceSize=256m \
  -XX:ReservedCodeCacheSize=128m \
  -XX:+UseStringDeduplication \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/tmp/heapdump.hprof \
  -XX:+ExitOnOutOfMemoryError \
  -Xlog:gc*:stdout:time,uptime:filecount=3,filesize=10m \
  -Djava.security.egd=file:/dev/./urandom"
```

```bash
# Entrypoint Dockerfile tipico per Spring Boot
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
```

### Metaspace e Code Cache

**Metaspace** contiene i metadati delle classi caricate dalla JVM. Cresce con il numero di classi caricate (framework, librerie, classi generate a runtime). Non ha limite di default — può crescere indefinitamente e causare OOM.

```bash
# Impostazioni Metaspace consigliate per microservizi
-XX:MetaspaceSize=128m        # Soglia per primo GC di Metaspace (non il max)
-XX:MaxMetaspaceSize=256m     # Limite assoluto — previene crescita incontrollata

# Per applicazioni con molte classi generate (Hibernate, cglib, Groovy):
-XX:MaxMetaspaceSize=384m
```

**Code Cache** contiene il codice nativo compilato dal JIT. Se si esaurisce, la JVM deoptimizza il codice → degrado performance drastico.

```bash
# Code Cache — Default 240 MB in JDK 11+, aumentare per app grandi
-XX:ReservedCodeCacheSize=256m   # Per microservizi standard
-XX:ReservedCodeCacheSize=512m   # Per app grandi con molti metodi hot (es. Hibernate ORM)
-XX:+UseCodeCacheFlushing         # Permette flush parziale se si avvicina al limite
```

```bash
# Monitoraggio Code Cache via JMX/jcmd
jcmd <pid> VM.native_memory summary
# Cerca "Code" nella sezione Non-heap:
# Code (CodeCache + CompileQueue + CodeHeap)
```

### Thread Stack e Concorrenza

Ogni thread JVM alloca uno stack. Con `-Xss` si controlla la dimensione per thread.

```bash
# Default: 512k-1MB per thread (dipende da OS e JVM version)
# Per microservizi con molti thread (Tomcat, Jetty):
-Xss512k     # 512 KB per thread — sicuro per la maggior parte dei casi

# Con 200 thread: 200 × 512k = 100 MB off-heap solo per stack
# Tenerne conto nel budget memoria off-heap
```

**Virtual Threads (Java 21 + Project Loom):**

```java
// Spring Boot 3.2+ — abilitare Virtual Threads
// application.yml
spring:
  threads:
    virtual:
      enabled: true

# Con Virtual Threads: thread stack overhead è trascurabile
# Non è più necessario dimensionare il pool di thread Tomcat
# -Xss può restare al default — i virtual thread sono leggeri (<KB)
```

### JVM 17 vs 21 — Differenze Rilevanti per Container

| Feature | Java 17 (LTS) | Java 21 (LTS) |
|---|---|---|
| Generational ZGC | No | Sì (`-XX:+ZGenerational`) |
| Virtual Threads | Preview | GA (Project Loom) |
| Compact Heap | Parziale | Migliorato |
| Sealed Classes | GA | GA |
| Pattern Matching | Parziale | GA |
| ZGC production-ready | No | Sì |

!!! tip "Scegli Java 21 per nuovi progetti"
    Java 21 è l'LTS corrente (fino al 2031). I miglioramenti al GC (ZGC generazionale) e i Virtual Threads rendono Java 21 superiore a Java 17 per microservizi K8s. La migrazione da 17 a 21 è solitamente non-breaking.

---

## Profiling: async-profiler e JFR

### async-profiler — Profiling a basso overhead in produzione

async-profiler è un profiler sampling a basso overhead (<3% CPU) che funziona anche in container senza accesso root completo.

```bash
# 1. Scaricare async-profiler nel container (o incluso nell'immagine base)
wget https://github.com/async-profiler/async-profiler/releases/latest/download/async-profiler-linux-x64.tar.gz
tar -xzf async-profiler-linux-x64.tar.gz

# 2. Avviare profiling CPU per 30 secondi sul processo JVM
./asprof -d 30 -f /tmp/flamegraph.html $(pgrep java)

# 3. Profiling allocazioni heap (trova chi alloca troppo)
./asprof -e alloc -d 30 -f /tmp/alloc-flamegraph.html $(pgrep java)

# 4. Profiling lock contention
./asprof -e lock -d 30 -f /tmp/lock-flamegraph.html $(pgrep java)
```

```bash
# Accedere al flamegraph fuori dal container
kubectl cp <namespace>/<pod>:/tmp/flamegraph.html ./flamegraph.html

# Alternativa: port-forward se l'app espone async-profiler via HTTP
# (richiede integrazione con py-spy o similar per Spring Boot Actuator)
```

### JFR (Java Flight Recorder) — Diagnostica integrata

JFR è integrato nella JVM da Java 11+ e ha overhead <1%. Ideale per diagnostica in produzione.

```bash
# Avviare una JFR recording tramite jcmd (dentro il container)
kubectl exec -it <pod> -- jcmd 1 JFR.start duration=60s filename=/tmp/recording.jfr

# Aspettare il termine e copiare fuori
kubectl cp <namespace>/<pod>:/tmp/recording.jfr ./recording.jfr

# Analizzare con JDK Mission Control (GUI locale)
# Download: https://www.oracle.com/java/technologies/javase/products-jmc8-downloads.html
```

```bash
# Abilitare JFR continuo all'avvio (bassa overhead, sempre attivo)
JAVA_OPTS="$JAVA_OPTS \
  -XX:StartFlightRecording=disk=true,maxage=1h,maxsize=500m,\
dumponexit=true,filename=/tmp/jfr/"
```

```bash
# Analisi rapida da CLI con jfr tool (incluso in JDK 17+)
jfr print --events GarbageCollection /tmp/recording.jfr | head -100
jfr summary /tmp/recording.jfr
```

!!! tip "JFR in Kubernetes — persistent volume"
    Monta un PVC o usa un sidecar per raccogliere i file JFR prima che il pod si riavvii. Alternativa: usa `-XX:FlightRecorderOptions=dumponexit=true` e configura un InitContainer per esfiltrare i file verso object storage (S3/GCS) all'uscita.

---

## OOMKiller: Riconoscimento e Prevenzione

### Come riconoscere un OOM kill

Quando il container supera il `memory.limit`, il kernel Linux uccide il processo con **SIGKILL** (exit code **137** = 128 + 9).

```bash
# Verificare se un pod è stato OOM-killed
kubectl describe pod <pod-name> | grep -A 5 "Last State"
# Output tipico:
#   Last State:     Terminated
#     Reason:       OOMKilled
#     Exit Code:    137

# Storico eventi del namespace
kubectl get events --sort-by='.lastTimestamp' | grep OOMKill

# Metriche container_oom_events (se Prometheus è configurato)
container_oom_events_total{namespace="production", pod=~"my-service.*"}
```

```bash
# Log del nodo (richiede accesso al nodo o DaemonSet)
dmesg | grep -i "oom\|killed process"
# Output:
# [123456.789] Out of memory: Kill process 12345 (java) score 987 or sacrifice child
# [123456.790] Killed process 12345 (java) total-vm:1048576kB, anon-rss:524288kB

# Verificare tramite /proc (dentro container se exit code 137)
# Il pod sarà in stato CrashLoopBackOff se si riavvia continuamente
kubectl get pods -w | grep my-service
```

### Strategie di Prevenzione

```bash
# Strategia 1: ExitOnOutOfMemoryError — fail fast invece di degradare
# La JVM esce immediatamente quando non può allocare heap
# Kubernetes riavvia il pod — meglio che un pod zombie con OOM continui
-XX:+ExitOnOutOfMemoryError

# Strategia 2: HeapDump automatico per diagnostica post-mortem
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/dumps/heapdump-$(hostname).hprof
# (Montare /dumps su un PVC per persistenza tra restart)

# Strategia 3: GC overhead circuit breaker
# La JVM lancia OutOfMemoryError se GC impiega >98% del tempo
# con <2% di heap liberato — evita loop infiniti di GC
# Questo è il comportamento di default, NON disabilitarlo con:
# -XX:-UseGCOverheadLimit  ← NON USARE
```

```yaml
# Kubernetes: impostare sempre request = limit per QoS Guaranteed
# Questo previene che il pod venga schedulato su nodi senza memoria sufficiente
# e riduce la probabilità di OOM per overcommit del nodo
resources:
  requests:
    memory: "768Mi"  # Uguale a limits per QoS Guaranteed
    cpu: "250m"
  limits:
    memory: "768Mi"  # Stesso valore = QoS Guaranteed
    cpu: "1000m"
```

---

## JVM vs GraalVM Native Image

### Confronto Caratteristiche

| Dimensione | JVM (JIT) | GraalVM Native Image |
|---|---|---|
| **Startup time** | 2-10s (Spring Boot JIT) | 50-200ms |
| **Memory footprint** | 200-500 MB (warm) | 50-150 MB |
| **Throughput (warm)** | Eccellente (JIT ottimizza) | Buono (AOT, no JIT) |
| **Latenza p99 (cold)** | Alta nei primi minuti | Consistente da subito |
| **Profiling** | async-profiler, JFR, JMX | Limitato (no JIT info) |
| **Debugging** | Completo | Limitato |
| **Compatibilità librerie** | Totale | Richiede reflection config |
| **Build time** | ~30s | 3-10 minuti |
| **Use case ideale** | Workload long-running, batch | Scale-to-zero, FaaS, sidecar |

### Quando scegliere JVM vs Native

```
JVM (JIT) — scegliere quando:
├── Il servizio gira 24/7 (warm JIT = massimo throughput)
├── Il team usa profiling intensivo (async-profiler, JFR)
├── Si usano librerie con reflection complessa (Hibernate ORM, dynamic proxies)
├── Il container ha >512 MB memory limit
└── Startup time non è un requisito critico

GraalVM Native — scegliere quando:
├── Scale-to-zero Kubernetes (HPA scala a 0, startup critico)
├── AWS Lambda / Azure Functions / Cloud Run
├── Memory limit container <256 MB
├── Latenza p99 consistente fin dal primo request
└── Quarkus o Micronaut (framework native-first)
```

```bash
# Build Native Image con Spring Boot 3.x (Maven)
./mvnw -Pnative native:compile

# Build Native Image con Quarkus
./mvnw package -Dnative -Dquarkus.native.container-build=true

# Dockerfile multi-stage per native image
FROM ghcr.io/graalvm/native-image:21 AS builder
WORKDIR /app
COPY . .
RUN ./mvnw -Pnative native:compile -DskipTests

FROM debian:bookworm-slim
COPY --from=builder /app/target/my-service /app/my-service
ENTRYPOINT ["/app/my-service"]
# Nessun JVM needed — binario standalone
```

!!! warning "Native Image e reflection"
    GraalVM Native Image esegue la compilazione AOT: tutto ciò che usa reflection, proxy dinamici, o classpath scanning deve essere dichiarato esplicitamente in file JSON di configurazione (`reflect-config.json`, `proxy-config.json`). Spring Boot 3.x e Quarkus gestiscono la maggior parte automaticamente, ma librerie di terze parti potrebbero richiedere configurazione manuale.

---

## Best Practices

**Heap e memoria:**
- Usa sempre `-XX:MaxRAMPercentage` invece di `-Xmx` fisso — si adatta automaticamente al `memory.limit` del container senza dover aggiornare il Dockerfile ad ogni cambio di limit.
- Non usare `-Xms` uguale a `-Xmx` in Kubernetes — impedisce alla JVM di rilasciare memoria al OS durante periodi di basso traffico. Usa invece `-XX:InitialRAMPercentage=50.0`.
- Lascia sempre almeno 200-300 MB liberi dal heap per l'off-heap (Metaspace, Code Cache, thread stack, buffers).

**GC:**
- Inizia sempre con G1GC — è il default, ben testato, e funziona bene per la maggior parte dei carichi.
- Passa a ZGC (Java 21) solo se hai misurato pause G1GC >50ms con impatto reale su SLA.
- Non micro-ottimizzare flag GC senza dati di profiling reali — il rischio di peggiorare è alto.

**Produzione:**
- Abilita sempre `-XX:+HeapDumpOnOutOfMemoryError` con un path su PVC — senza heap dump, diagnosticare un OOM è quasi impossibile.
- Usa `-XX:+ExitOnOutOfMemoryError` per fail-fast: un pod che si riavvia velocemente è meglio di un pod zombie con memoria esaurita.
- Aggiungi `-Xlog:gc*:stdout` per avere i log GC in stdout — visibili con `kubectl logs` senza bisogno di accedere al container.

!!! tip "Baseline consigliata per Spring Boot su Kubernetes"
    Container da 1 GiB con G1GC e Java 21: `-XX:+UseG1GC -XX:MaxRAMPercentage=65.0 -XX:InitialRAMPercentage=50.0 -XX:MaxMetaspaceSize=256m -XX:ReservedCodeCacheSize=128m -XX:+HeapDumpOnOutOfMemoryError -XX:+ExitOnOutOfMemoryError`

---

## Troubleshooting

### Scenario 1 — Pod in CrashLoopBackOff con exit code 137

**Sintomo:** Il pod si riavvia continuamente, `kubectl describe pod` mostra `OOMKilled` e `Exit Code: 137`.

**Causa:** Il processo JVM (heap + off-heap) supera il `memory.limit` del container. Possibili cause: heap troppo grande rispetto al limit, Metaspace illimitato che cresce, memory leak applicativo.

**Soluzione:**

```bash
# 1. Verificare il profilo memoria attuale
kubectl top pod <pod-name> --containers

# 2. Controllare l'heap attuale nei log all'avvio
# Cercare: "Heap size: X MB" o "-XX:MaxRAMPercentage"
kubectl logs <pod-name> | grep -i "heap\|memory\|MaxRAM"

# 3. Ridurre MaxRAMPercentage e aggiungere tetto Metaspace
# Prima: -XX:MaxRAMPercentage=75.0 (nessun MaxMetaspaceSize)
# Dopo:  -XX:MaxRAMPercentage=65.0 -XX:MaxMetaspaceSize=256m

# 4. Aumentare il memory limit del container (se il servizio ne ha realmente bisogno)
kubectl set resources deployment/my-service --limits=memory=1.5Gi

# 5. Verificare heap dump se disponibile
# Se -XX:+HeapDumpOnOutOfMemoryError era attivo, analizzare con Eclipse MAT
# per identificare memory leak
```

### Scenario 2 — Performance degrada progressivamente dopo ore di uptime

**Sintomo:** Le latenze p99 aumentano nel tempo. `kubectl top` mostra CPU alta. I log GC mostrano Full GC frequenti.

**Causa:** Memory leak applicativo (oggetti non vengono garbage collected), oppure heap undersized che causa GC troppo frequente.

**Soluzione:**

```bash
# 1. Verificare frequenza GC nei log
kubectl logs <pod-name> | grep -i "gc\|pause" | tail -50

# 2. Controllare heap usage tramite Actuator (Spring Boot)
curl http://localhost:8080/actuator/metrics/jvm.memory.used?tag=area:heap
curl http://localhost:8080/actuator/metrics/jvm.gc.pause

# 3. Avviare JFR recording per analisi
kubectl exec -it <pod> -- jcmd 1 JFR.start duration=120s filename=/tmp/leak.jfr
kubectl cp <namespace>/<pod>:/tmp/leak.jfr ./leak.jfr
# Aprire con JDK Mission Control, cercare oggetti che crescono nel tempo

# 4. Se confermato memory leak: heap dump
kubectl exec -it <pod> -- jcmd 1 GC.heap_dump /tmp/heap.hprof
kubectl cp <namespace>/<pod>:/tmp/heap.hprof ./heap.hprof
# Analizzare con Eclipse MAT o IntelliJ Heap Analyzer
```

### Scenario 3 — Startup lento — il pod impiega >30s prima di essere ready

**Sintomo:** Il container parte ma la readiness probe fallisce per 30-60s. `kubectl describe pod` mostra `Readiness probe failed` nella fase iniziale.

**Causa:** La JVM impiega tempo a caricare le classi e il JIT a ottimizzare il codice (JVM warmup). Compounding: classpath scanning di Spring Boot, inizializzazione Hibernate.

**Soluzione:**

```bash
# 1. Aggiungere Class Data Sharing (CDS) per accelerare il load delle classi
# Step 1: generare l'archivio CDS
java -Xshare:dump -XX:SharedArchiveFile=/app/app-cds.jsa \
     -XX:SharedClassListFile=/app/classlist.txt -jar /app/app.jar

# Step 2: usarlo all'avvio
java -Xshare:on -XX:SharedArchiveFile=/app/app-cds.jsa \
     $JAVA_OPTS -jar /app/app.jar

# 2. Spring AOT (Spring Boot 3.x) — pre-compila parte del context
./mvnw spring-boot:build-image -Pnative  # oppure solo AOT senza native

# 3. Aumentare initialDelaySeconds nella readiness probe
# Non è una soluzione, è un workaround — ma evita restart prematuri
readinessProbe:
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 6
```

### Scenario 4 — Latenze spike improvvisi (stop-the-world GC pause)

**Sintomo:** Ogni N minuti ci sono spike di latenza da 500ms-2s. I log GC mostrano `[GC pause (G1 Humongous Allocation)]` o `Full GC`.

**Causa:** Oggetti "humongous" (>50% della G1 region size) che vengono allocati nel Old Gen bypassando Young Gen. Oppure IHOP (Initiating Heap Occupancy Percent) troppo alto che ritarda il marking cycle fino al Full GC.

**Soluzione:**

```bash
# 1. Identificare le allocazioni humongous nei log GC
kubectl logs <pod> | grep -i "humongous\|full gc"

# 2. Aumentare G1HeapRegionSize per ridurre le allocazioni humongous
# Se le allocazioni sono ~1 MB → imposta region size a 4 MB
# Oggetto humongous = > 50% region size → con 4 MB region, serve >2 MB per essere humongous
-XX:G1HeapRegionSize=4m

# 3. Abbassare IHOP per triggherare il GC cycle prima
# Default: 45%, abbassare a 35% se Full GC frequenti
-XX:InitiatingHeapOccupancyPercent=35

# 4. Passare a ZGC se G1GC non è sufficiente
-XX:+UseZGC -XX:+ZGenerational  # Java 21

# 5. Verificare con async-profiler le allocazioni
./asprof -e alloc -d 60 -f /tmp/alloc.html $(pgrep java)
# Aprire alloc.html: mostra chi alloca oggetti grandi
```

---

## Relazioni

??? info "Kubernetes Resource Management — Approfondimento"
    La JVM opera dentro i vincoli definiti da `requests` e `limits` Kubernetes. Una configurazione JVM corretta dipende da una comprensione dei QoS class e dell'OOMKiller del kernel, descritti in dettaglio in Resource Management.

    **Approfondimento completo →** [Kubernetes Resource Management](../../containers/kubernetes/resource-management.md)

??? info "Java Spring Boot — JVM defaults"
    Spring Boot 3.x su Java 21 con Virtual Threads attivi cambia il profilo di utilizzo della JVM: molti più thread (virtuali, leggeri) ma lo stesso modello di heap. Le configurazioni JVM di questo documento si applicano direttamente a Spring Boot.

    **Approfondimento completo →** [Java Spring Boot](../linguaggi/java-spring-boot.md)

??? info "Java Quarkus — JVM vs Native mode"
    Quarkus supporta sia modalità JVM (stesse configurazioni di questo documento) che Native Image (GraalVM). La sezione JVM vs Native di questo documento integra il confronto dettagliato di Quarkus.

    **Approfondimento completo →** [Java Quarkus](../linguaggi/java-quarkus.md)

---

## Riferimenti

- [JDK 21 GC Tuning Guide](https://docs.oracle.com/en/java/javase/21/gctuning/)
- [ZGC — The Z Garbage Collector (OpenJDK)](https://wiki.openjdk.org/display/zgc/Main)
- [G1GC Tuning Guide](https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html)
- [async-profiler GitHub](https://github.com/async-profiler/async-profiler)
- [JDK Mission Control (JFR)](https://www.oracle.com/java/technologies/javase/products-jmc8-downloads.html)
- [Container-aware JVM — JEP 338](https://openjdk.org/jeps/338)
- [Shenandoah GC](https://openjdk.org/projects/shenandoah/)
- [Eclipse MAT (Memory Analyzer)](https://eclipse.dev/mat/)
