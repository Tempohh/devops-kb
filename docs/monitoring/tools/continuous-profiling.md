---
title: "Continuous Profiling"
slug: continuous-profiling
category: monitoring
tags: [profiling, observability, performance, pyroscope, parca, ebpf, cncf, opentelemetry]
search_keywords: [continuous profiling, profiling continuo, flame graph, flamegraph, Grafana Pyroscope, Pyroscope, CNCF Parca, Parca Agent, pprof, eBPF profiling, CPU profiling, memory profiling, heap profiling, quarto pilastro osservabilità, fourth pillar observability, OTel Profiling signal, sampling profiler, on-CPU profiling, off-CPU profiling, symbolication, debug symbols, hot path, hot loop, memory leak detection, performance regression]
parent: monitoring/tools
related: [monitoring/fondamentali/tre-pilastri-osservabilita, monitoring/fondamentali/opentelemetry, monitoring/tools/prometheus, monitoring/tools/grafana, monitoring/tools/otel-collector-kubernetes]
official_docs: https://grafana.com/docs/pyroscope/latest/
status: complete
difficulty: intermediate
last_updated: 2026-09-27
---

# Continuous Profiling

## Panoramica

Il **continuous profiling** (profiling continuo) raccoglie in modo permanente e a basso overhead i profili di CPU, memoria, e altre risorse di un'applicazione in produzione, correlandoli nel tempo e per servizio. È spesso citato come il **"quarto pilastro" dell'osservabilità**, accanto a metriche, log e tracce: mentre le tracce rispondono a "quale richiesta è lenta", il profiling risponde a "quale funzione, o quale riga di codice, consuma CPU o memoria" — a livello di **flame graph**, senza dover redistribuire un binario instrumentato ad-hoc per il debug.

Storicamente il profiling era uno strumento "puntuale": si attivava `pprof` manualmente per qualche minuto su un singolo processo quando si sospettava un problema, poi si disattivava. Il continuous profiling ribalta l'approccio: raccoglie campioni **sempre**, su **tutta la flotta**, con overhead trascurabile (tipicamente <1-2% CPU) grazie a sampling statistico o a strumentazione **eBPF** che non richiede modifiche al codice applicativo. Il risultato è una serie storica di profili interrogabile esattamente come una metrica Prometheus, ma con granularità a livello di stack trace.

Si usa quando occorre capire l'origine esatta (funzione, riga, allocazione) di un consumo di CPU o memoria anomalo, specialmente in produzione dove riprodurre il problema in locale è difficile o impossibile. Non sostituisce metriche, log o tracce: si correla con essi. Non si usa per capire "quale richiesta è lenta attraverso i microservizi" (quello è compito del tracing) né per il debug interattivo passo-passo (quello è compito di un debugger).

## Concetti Chiave

!!! note "Cos'è un profilo"
    Un **profilo** è una fotografia aggregata di dove un programma spende una risorsa (CPU, memoria, lock contention, I/O) durante un intervallo di tempo. È rappresentato come un albero di stack trace pesati: ogni nodo è una funzione, il peso è il tempo/memoria attribuito a quella funzione e ai suoi discendenti.

    - **Sample**: singola osservazione dello stack di chiamata in un istante (per CPU) o di un'allocazione (per memoria)
    - **Flame Graph**: visualizzazione degli stack aggregati, larghezza = peso, altezza = profondità della call stack
    - **Symbolication**: risoluzione degli indirizzi di memoria/istruzione in nomi di funzione e numeri di riga leggibili
    - **Labels**: come le metriche Prometheus, i profili portano label (`service`, `pod`, `version`) per filtrare e confrontare

### Tipi di Profiling

| Tipo | Cosa misura | Caso d'uso tipico |
|---|---|---|
| **CPU profiling (on-CPU)** | Tempo speso eseguendo codice sulla CPU | Hot loop, funzione che consuma troppa CPU |
| **Memory / Heap profiling** | Allocazioni di memoria per stack trace | Memory leak, allocazioni eccessive, GC pressure |
| **Off-CPU profiling** | Tempo speso in attesa (I/O, lock, syscall) | Thread bloccati, contention su mutex, I/O lento |
| **Goroutine / Thread profiling** | Numero e stato di goroutine/thread | Goroutine leak, deadlock |
| **Wall-clock profiling** | Tempo totale (on-CPU + off-CPU) | Visione end-to-end della latenza per richiesta |

### Sampling vs Instrumentazione

!!! note "Perché il sampling è la chiave dell'overhead basso"
    Il continuous profiling non traccia ogni singola istruzione (troppo costoso): campiona lo stack a intervalli regolari (es. 100Hz per CPU) o su ogni N-esima allocazione. Statisticamente, le funzioni che consumano di più appaiono più spesso nei campioni — un flame graph accurato emerge senza dover strumentare il codice.

    - **eBPF-based**: il kernel Linux campiona direttamente lo stack dei processi, zero modifiche al codice, funziona anche su binari già in esecuzione (es. Parca Agent, Pyroscope eBPF)
    - **Language-runtime-based**: il runtime del linguaggio espone un profiler nativo (`pprof` in Go, `async-profiler` in JVM, `py-spy` in Python) — richiede un piccolo agente in-process o accesso al processo

## Architettura / Come Funziona

### Pipeline Generale

```
Applicazioni / Host
       │
       ├── Profiler in-process (pprof, async-profiler, py-spy)
       │        oppure
       ├── Agent eBPF (DaemonSet, un solo agente per nodo, profila TUTTI i processi)
       │
       ▼ push periodico (10-15s) via HTTP/gRPC
┌─────────────────────┐
│  Profiling Server    │  ← riceve, deduplica, comprime (Pyroscope / Parca Server)
└──────────┬───────────┘
           │
    ┌──────┴──────┐
    │   Storage    │  ← columnar/object storage (S3/GCS), ottimizzato per profili compressi
    └──────┬──────┘
           │
┌──────────┴───────────┐
│   Query + Flame Graph │  ← Grafana Explore Profiles / Parca UI
└───────────────────────┘
```

**Vantaggio dell'agente eBPF a livello di nodo**: un singolo DaemonSet profila l'intero nodo (tutti i container/pod), senza dover instrumentare o riavviare ogni singola applicazione — utile per adottare il profiling su flotte esistenti senza modifiche al deployment.

### Correlazione con gli Altri Segnali

Il valore massimo si ottiene correlando un picco di CPU visto in una metrica Prometheus con il flame graph dello stesso intervallo temporale, e con il trace_id della richiesta lenta:

```
1. Alert Prometheus: cpu_usage_percent > 90% su pod payment-service-7f8d
2. Grafana dashboard: il picco è iniziato alle 14:32 e dura 6 minuti
3. Grafana Explore Profiles: seleziona service=payment-service, range 14:30-14:38
   → Flame graph mostra il 70% del tempo CPU in `json.Marshal()` dentro `serializeOrder()`
4. Conclusione: una regressione nel serializzatore introdotta dal deploy delle 14:29
   Nessuna riproduzione locale necessaria — il profilo di produzione è la prova.
```

## Configurazione & Pratica

### Grafana Pyroscope — Deploy Kubernetes (Helm)

```bash
# Aggiungi il repo Helm e installa Pyroscope in modalità monolitica
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install pyroscope grafana/pyroscope \
  --namespace observability --create-namespace \
  --set pyroscope.storage.backend=s3 \
  --set pyroscope.storage.s3.bucket_name=my-pyroscope-profiles
```

```yaml
# values.yaml — eBPF profiler come DaemonSet, profila TUTTI i pod del nodo
# senza modificare le applicazioni esistenti
ebpf:
  enabled: true
  daemonset:
    resources:
      limits:
        cpu: 200m
        memory: 256Mi
  config:
    targets:
      - service_name_label: "app.kubernetes.io/name"  # deriva il nome servizio dalle label pod
```

### Instrumentazione in-process (Go, quando serve granularità applicativa)

```go
// main.go — invio profili CPU/heap direttamente da un'app Go a Pyroscope
package main

import (
    "github.com/grafana/pyroscope-go"
)

func main() {
    _, err := pyroscope.Start(pyroscope.Config{
        ApplicationName: "payment-service",
        ServerAddress:   "http://pyroscope:4040",
        Tags: map[string]string{
            "environment": "production",
            "version":     "1.4.2",
        },
        ProfileTypes: []pyroscope.ProfileType{
            pyroscope.ProfileCPU,
            pyroscope.ProfileAllocObjects,
            pyroscope.ProfileAllocSpace,
            pyroscope.ProfileInuseObjects,
            pyroscope.ProfileInuseSpace,
        },
    })
    if err != nil {
        panic(err)
    }
    // ... avvio applicazione ...
}
```

### CNCF Parca — Alternativa eBPF-native

```yaml
# parca-agent-daemonset.yaml — profiling a livello di nodo, zero instrumentazione
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: parca-agent
spec:
  template:
    spec:
      hostPID: true          # necessario per profilare processi su tutto il nodo
      containers:
        - name: parca-agent
          image: ghcr.io/parca-dev/parca-agent:v0.34.0
          securityContext:
            privileged: true # richiesto per attach eBPF
          args:
            - "--node=$(NODE_NAME)"
            - "--remote-store-address=parca-server:7070"
            - "--remote-store-insecure"
          env:
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
```

```bash
# Query dei profili raccolti via CLI Parca
parca query \
  --start="2026-09-27T14:30:00Z" \
  --end="2026-09-27T14:38:00Z" \
  --query='{node_name="ip-10-0-1-23",__name__="cpu"}'
```

### Integrazione con OpenTelemetry (OTel Profiling Signal)

Dal 2025 OpenTelemetry ha stabilizzato il **profiling come quarto signal** (accanto a traces, metrics, logs), permettendo di raccogliere profili con lo stesso Collector già usato per gli altri segnali:

```yaml
# otel-collector-config.yaml — pipeline profiles accanto a traces/metrics/logs
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  otlp/pyroscope:
    endpoint: "pyroscope:4317"

service:
  pipelines:
    profiles:               # pipeline dedicata al signal "profiles"
      receivers: [otlp]
      exporters: [otlp/pyroscope]
```

Questo elimina la necessità di un agente separato quando l'SDK applicativo supporta già l'export OTel per il profiling, e permette di correlare `trace_id` e profilo tramite lo stesso Collector già documentato in [OTel Collector su Kubernetes](./otel-collector-kubernetes.md).

## Best Practices

!!! tip "Adotta prima l'agente eBPF a livello di nodo"
    Prima di instrumentare singole applicazioni, deploya l'agente eBPF (Pyroscope eBPF o Parca Agent) come DaemonSet: copre l'intera flotta in un colpo solo, senza toccare il codice. Aggiungi instrumentazione in-process solo dove serve granularità applicativa extra (es. tag custom per business logic).

!!! warning "Debug symbols mancanti nei container distroless/scratch"
    Immagini container minimali (distroless, `scratch`) spesso non includono i debug symbols necessari per la symbolication. Il flame graph risultante mostra indirizzi esadecimali invece di nomi di funzione. Soluzione: pubblicare i debug symbols separatamente (debuginfod, o side-car con symbols) oppure includerli in un layer immagine dedicato solo per gli ambienti dove serve debug approfondito.

**Pattern consigliati:**
- Retention breve per i profili raw (7-14 giorni) — il valore decade rapidamente come per le tracce
- Correlare sempre profili e metriche tramite gli stessi label (`service`, `pod`, `version`) per poter passare da un picco su Grafana al flame graph corrispondente in un click
- Usare i profili differenziali ("diff flame graph" tra due deploy) per individuare regressioni di performance introdotte da una release
- Limitare la frequenza di sampling CPU a 100Hz — oltre non aumenta la precisione ma aumenta overhead e volume dati

**Anti-pattern da evitare:**
- Attivare profiling `pprof` manuale "on-demand" solo quando il problema è già in corso — spesso il picco è già passato quando si attiva
- Profilare senza label/tag per ambiente o versione, rendendo impossibile isolare quale deploy ha introdotto una regressione
- Ignorare l'overhead della symbolication runtime: su binari molto grandi va cacheata, non ricalcolata ad ogni query

## Troubleshooting

**Scenario 1: Overhead CPU imprevisto su nodi ad alta cardinalità di stack**

```
Sintomo: dopo il deploy dell'agente eBPF, cpu_usage del nodo sale del 5-8%
Causa:   troppi processi con stack molto profondi (>200 frame), symbolication
         eseguita troppo frequentemente lato agente

Soluzione:
1. Riduci la frequenza di sampling (es. da 100Hz a 19Hz per profili CPU non critici)
2. Verifica se la symbolication può essere spostata lato server invece che lato agente:
   --agent-symbolization=false (Parca) oppure sample-rate più basso in Pyroscope eBPF
3. Escludi processi non rilevanti via label selector nel config dell'agente
```

**Scenario 2: Simboli non risolti, flame graph mostra solo indirizzi esadecimali**

```
Sintomo: flame graph con frame tipo "0x7f8a2c001230" invece di nomi funzione
Causa:   binario compilato senza debug symbols, o simboli strippati nell'immagine
         container di produzione

Soluzione:
- Verifica presenza symbols: file ./mio-binario | grep "not stripped"
- Se strippati: pubblica i symbols separatamente e configura debuginfod
- Per Go: assicurati di non compilare con -ldflags="-s -w" in produzione se serve
  profiling leggibile, oppure mantieni una build con symbols separata solo per debug
```

**Scenario 3: Costi di storage dei profili in crescita rapida**

```
Sintomo: bucket S3 dei profili cresce di decine di GB/giorno
Causa:   retention troppo lunga, o troppi profile type attivi (CPU+heap+goroutine
         su ogni servizio, ad alta frequenza)

Soluzione:
1. Riduci retention a 7-14 giorni (i profili storici hanno valore decrescente,
   come le tracce)
2. Disattiva profile type non necessari per servizi a basso rischio memory leak
   (es. disattiva ProfileAllocObjects se già monitori ProfileInuseSpace)
3. Verifica compressione attiva lato storage backend (Pyroscope/Parca comprimono
   nativamente, controlla configurazione storage.s3)
```

**Scenario 4: Flame graph mostra tempo "mancante" rispetto alla latenza reale**

```
Sintomo: la latenza totale di una richiesta (da traccia) è 2s, ma il profilo
         CPU nello stesso intervallo mostra solo 200ms di tempo attribuito
Causa:   il profilo CPU cattura solo tempo on-CPU; il resto è tempo off-CPU
         (attesa I/O, lock, syscall bloccanti) non incluso nel profilo di default

Soluzione:
- Attiva off-CPU profiling se supportato dal profiler in uso (es. Parca Agent
  supporta profili off-CPU sperimentali via eBPF)
- Correla con la traccia distribuita per capire se il tempo mancante è I/O
  (query DB lenta, chiamata di rete) — è compito del tracing, non del profiling
```

## Relazioni

??? info "I Tre Pilastri dell'Osservabilità — dove si inserisce il profiling"
    Il continuous profiling è spesso chiamato "quarto pilastro": completa metriche, log e tracce rispondendo alla domanda "quale funzione/riga di codice consuma la risorsa", con lo stesso approccio always-on delle metriche ma granularità a livello di stack trace.

    **Approfondimento completo →** [I Tre Pilastri dell'Osservabilità](../fondamentali/tre-pilastri-osservabilita.md)

??? info "OpenTelemetry — Standard di Instrumentazione"
    Dal 2025 OTel include il profiling come signal stabilizzato, permettendo di raccogliere profili con lo stesso Collector usato per traces/metrics/logs.

    **Approfondimento completo →** [OpenTelemetry](../fondamentali/opentelemetry.md)

??? info "Prometheus — Correlazione con le Metriche"
    Un picco osservato in una metrica Prometheus (es. `cpu_usage_percent`) è il punto di partenza tipico per aprire il flame graph dello stesso intervallo temporale in Pyroscope/Parca.

    **Approfondimento completo →** [Prometheus](./prometheus.md)

??? info "Grafana — Visualizzazione dei Profili"
    Grafana integra nativamente Pyroscope tramite il datasource "Explore Profiles", permettendo di navigare da dashboard di metriche al flame graph corrispondente.

    **Approfondimento completo →** [Grafana](./grafana.md)

??? info "OTel Collector su Kubernetes — Pipeline Condivisa"
    Il Collector già usato per traces/metrics/logs può instradare anche il signal profiles verso Pyroscope o Parca, evitando un agente separato quando l'SDK applicativo lo supporta.

    **Approfondimento completo →** [OTel Collector su Kubernetes](./otel-collector-kubernetes.md)

## Riferimenti

- [Grafana Pyroscope — Documentazione Ufficiale](https://grafana.com/docs/pyroscope/latest/)
- [CNCF Parca — Documentazione](https://www.parca.dev/docs/overview)
- [OpenTelemetry — Profiling Signal](https://opentelemetry.io/docs/specs/otel/profiles/)
- [Brendan Gregg — Flame Graphs](https://www.brendangregg.com/flamegraphs.html)
- [Go pprof — Profiling Go Programs](https://go.dev/blog/pprof)
- [eBPF.io — Introduzione a eBPF](https://ebpf.io/what-is-ebpf/)
