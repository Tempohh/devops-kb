---
title: "Model Serving — vLLM, TGI e Deployment"
slug: model-serving
category: ai
tags: [vllm, tgi, model-serving, inference, triton, ollama, autoscaling]
search_keywords: [vLLM, TGI text generation inference, model serving LLM, inference server, PagedAttention, continuous batching, speculative decoding, TTFT time to first token, throughput LLM, Triton inference server, Ollama serving, LoRA serving, autoscaling GPU, OpenAI compatible API, inference optimization]
parent: ai/mlops/_index
related: [ai/mlops/_index, ai/mlops/infrastruttura-gpu, ai/modelli/modelli-open-source, ai/mlops/pipeline-ml]
official_docs: https://docs.vllm.ai/
status: complete
difficulty: expert
last_updated: 2026-02-27
---

# Model Serving — vLLM, TGI e Deployment

## Panoramica

Il model serving per LLM presenta sfide uniche rispetto al serving di modelli ML classici. La generazione di testo è un processo **autoregressivo**: il modello genera un token alla volta, e ogni token dipende da tutti quelli precedenti. Questo crea un trade-off naturale tra latenza (importante per l'utente) e throughput (importante per il costo). Le soluzioni moderne come vLLM e TGI affrontano queste sfide con tecniche sofisticate: KV cache management, continuous batching, e speculative decoding.

Scegliere il serving framework giusto dipende dai requisiti: vLLM per throughput e production OpenAI-compatible API; TGI per integrazione HuggingFace; Triton per multi-model enterprise; Ollama per sviluppo e deployment semplice. In tutti i casi, il monitoring delle metriche specifiche LLM (TTFT, ITL, throughput, errori) è fondamentale.

## 1. Metriche di Serving LLM

Comprendere le metriche specifiche dell'inferenza LLM è prerequisito per qualsiasi discussione di serving.

| Metrica | Descrizione | Target |
|---------|-------------|--------|
| **TTFT** (Time to First Token) | Latenza dal momento della request al primo token nell'output | < 500ms per uso interattivo |
| **ITL** (Inter-Token Latency) | Tempo tra token successivi nella fase di generazione | < 50ms per testo fluido |
| **E2E Latency** | Tempo totale per completare la response | Dipende dalla lunghezza |
| **Throughput** | Token generati per secondo (su tutte le request) | > 1000 tok/s (serving) |
| **Requests/second** | Richieste completate al secondo | Dipende dal modello |
| **GPU Utilization** | % utilizzo GPU | > 70% (sotto-utilizzo = inefficienza) |

### Fasi dell'Inferenza

```
Request → [PREFILL PHASE] → [DECODE PHASE] → Response

PREFILL:
- Processa l'intero prompt in parallelo (1 forward pass)
- Calcola e salva KV cache per tutti i token input
- Costoso ma parallelizzabile — GPU-compute bound
- Durata: proporzionale a input_tokens

DECODE:
- Genera 1 token per step (autoregressivo)
- Ogni step richiede lettura dell'intera KV cache
- Memory-bandwidth bound (non compute bound)
- Durata: proporzionale a output_tokens × ITL
```

Il TTFT è dominato dalla fase di **prefill** (lunga per prompt lunghi). L'ITL è dominato dalla fase di **decode** (limitata dal bandwidth della VRAM).

## 2. vLLM — Il Gold Standard

vLLM è il framework open source più performante per serving LLM. Le sue innovazioni principali sono **PagedAttention** per la gestione efficiente del KV cache e il **continuous batching** per massimizzare la GPU utilization.

### Installazione e Configurazione Base

```bash
# Installazione
pip install vllm

# Avvio server OpenAI-compatible
vllm serve meta-llama/Llama-3.1-8B-Instruct \
    --dtype bfloat16 \
    --tensor-parallel-size 1 \        # numero di GPU
    --max-model-len 32768 \           # context window
    --max-num-seqs 256 \              # max request simultanee
    --gpu-memory-utilization 0.90 \   # % VRAM usata per vLLM
    --port 8000 \
    --api-key "my-secret-key"

# Con tensor parallelism su 2 GPU
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 2 \
    --dtype bfloat16 \
    --max-model-len 16384

# Quantizzazione AWQ per ridurre VRAM
vllm serve meta-llama/Llama-3.1-8B-Instruct \
    --quantization awq \
    --dtype auto

# Con prefix caching (riusa KV cache di prompt condivisi)
vllm serve model \
    --enable-prefix-caching \
    --max-num-batched-tokens 8192
```

### API Usage (OpenAI-Compatible)

```python
from openai import OpenAI

# vLLM espone un'API identica a OpenAI
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="my-secret-key"
)

# Completion
response = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[
        {"role": "system", "content": "Sei un esperto DevOps."},
        {"role": "user", "content": "Come si configura un Ingress nginx?"}
    ],
    max_tokens=1024,
    temperature=0.7,
    stream=True  # streaming supportato
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### PagedAttention — Come Funziona

```
Problema tradizionale:
Ogni request pre-alloca la VRAM per il KV cache del contesto massimo
Se max_seq_len=8192, ogni request usa KV cache da 8192 token
→ Ma la request media può usarne solo 500
→ 94% della KV cache è sprecata (frammentazione esterna)

PagedAttention (ispirato alla virtual memory degli OS):
- KV cache è gestita in "pages" di dimensione fissa (es. 16 token)
- Le pages vengono allocate e deallocate dinamicamente
- Request brevi usano poche pages, request lunghe ne usano molte
- Nessuna frammentazione: qualsiasi combinazione di request si ottimizza

Risultato:
- Fino a 24× miglioramento nel throughput rispetto a serving naive
- Memoria usata proporzionale ai token effettivi, non al max_seq_len
```

### Continuous Batching

```
Batching Tradizionale (Static):
Batch 1: Request A, B, C → aspetta che TUTTE finiscano → poi batch 2
Se A finisce subito ma B è molto lunga → GPU aspetta B con A slot vuoto

Continuous Batching (Dynamic):
Quando A finisce → viene rimossa dal batch
Immediatamente una nuova request D prende il posto di A
Il batch è sempre pieno (o quasi)
→ GPU utilization molto più alta
```

### LoRA Serving con vLLM

```bash
# Serve il modello base con supporto per più LoRA adapter
vllm serve meta-llama/Llama-3.1-8B-Instruct \
    --enable-lora \
    --max-loras 4 \                  # fino a 4 adapter in memoria
    --max-lora-rank 64 \
    --lora-modules \
        devops-expert=/path/to/devops-lora \
        security-expert=/path/to/security-lora
```

```python
# Uso con adapter specifico
response = client.chat.completions.create(
    model="devops-expert",  # usa il LoRA adapter "devops-expert"
    messages=[{"role": "user", "content": "Analizza questo Dockerfile"}]
)
```

### Benchmarking vLLM

```bash
# Benchmark throughput
python -m vllm.entrypoints.openai.api_server &
python benchmarks/benchmark_throughput.py \
    --backend vllm \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --num-prompts 1000 \
    --max-tokens 200

# Output:
# Throughput: 1234.56 requests/s
# Total time: 811.43s
# ...

# Benchmark latenza (TTFT e ITL)
python benchmarks/benchmark_latency.py \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --input-len 512 \
    --output-len 128 \
    --num-iters 100
```

## 3. HuggingFace TGI — Text Generation Inference

TGI è il serving framework di HuggingFace, con forte integrazione con l'ecosistema HF.

```bash
# Avvio con Docker (modo più semplice)
docker run --gpus all --shm-size 1g \
  -p 8080:80 \
  -v $PWD/models:/data \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id meta-llama/Meta-Llama-3.1-8B-Instruct \
  --dtype bfloat16 \
  --max-input-length 4096 \
  --max-total-tokens 8192 \
  --max-batch-prefill-tokens 8192 \
  --num-shard 1  # tensor parallelism

# Con quantizzazione (riduce VRAM)
docker run --gpus all -p 8080:80 \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id meta-llama/Meta-Llama-3.1-8B-Instruct \
  --quantize bitsandbytes  # o awq, gptq
```

```python
from huggingface_hub import InferenceClient

client = InferenceClient("http://localhost:8080")

# Chat completions
messages = [{"role": "user", "content": "Spiega come funziona il blue-green deployment"}]

# Streaming
for token in client.chat.completions.create(
    messages=messages,
    max_tokens=512,
    stream=True
):
    print(token.choices[0].delta.content, end="", flush=True)
```

**Differenze TGI vs vLLM:**

| Aspetto | vLLM | TGI |
|---------|------|-----|
| Throughput | Superiore (PagedAttention) | Buono |
| Integrazione HF | Standard | Nativa |
| LoRA serving | Si | Si (Adapter support) |
| Streaming | Si | Si |
| Model zoo | OpenAI-style API | HF format |
| Quantization | AWQ, GPTQ, FP8 | AWQ, GPTQ, BitsAndBytes |
| Community | Grande, attiva | HuggingFace ufficiale |

## 4. Ollama per Sviluppo

Ollama è la scelta più semplice per sviluppo locale e deployment edge. Non è ottimizzato per throughput alto.

```bash
# Serving base
ollama serve &

# Download e avvio modello
ollama pull llama3.1:8b
ollama run llama3.1:8b

# API REST
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'

# Tuning per serving (variabili ambiente)
OLLAMA_NUM_PARALLEL=4  # request parallele simultanee
OLLAMA_MAX_LOADED_MODELS=2  # modelli in VRAM contemporaneamente
OLLAMA_KEEP_ALIVE=5m  # mantieni modello in VRAM per N minuti
```

## 5. NVIDIA Triton Inference Server

Triton è la soluzione enterprise NVIDIA per multi-model serving con supporto per diversi backend (TensorRT, PyTorch, ONNX, vLLM).

```bash
# Struttura model repository
model_repository/
├── llama3_8b/
│   ├── config.pbtxt    # configurazione modello
│   └── 1/             # versione 1
│       └── model.py   # implementazione (Python backend)
└── llama3_70b/
    ├── config.pbtxt
    └── 1/
        └── model.py

# config.pbtxt per vLLM backend
name: "llama3_8b"
backend: "vllm"
max_batch_size: 0

input [
  {
    name: "text_input"
    data_type: TYPE_STRING
    dims: [ -1 ]
  }
]
output [
  {
    name: "text_output"
    data_type: TYPE_STRING
    dims: [ -1 ]
  }
]

instance_group [
  {
    kind: KIND_MODEL
    count: 1
  }
]
```

```bash
# Avvio Triton
docker run --gpus all -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $PWD/model_repository:/models \
  nvcr.io/nvidia/tritonserver:24.01-vllm-python-py3 \
  tritonserver --model-repository=/models

# gRPC client
pip install tritonclient[grpc]
```

## 6. Speculative Decoding

Lo speculative decoding usa un **modello draft** piccolo e veloce per proporre più token in batch, che il modello target grande verifica in parallelo.

```
Metodo tradizionale (1 token per step):
Target (70B): token1 → token2 → token3 → ...
Ogni step richiede 1 forward pass del modello grande (lento)

Speculative Decoding:
Draft (8B): genera token1, token2, token3, token4 (4 token in 1 step)
Target (70B): verifica 4 token in 1 forward pass (parallelo!)
              Se accetta tutti 4: +4 token con 1 pass del modello grande
              Se rifiuta al token3: scarti 3,4 e rigenera

Speedup: 2-4× per generazione (spesso ~2.5×)
Qualità: identica al modello target (rejection sampling garantisce equivalenza)
VRAM: aggiunge la VRAM del draft model
```

```bash
# vLLM con speculative decoding
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --speculative-model meta-llama/Llama-3.2-1B-Instruct \
    --num-speculative-tokens 5 \      # 5 token proposti per step
    --tensor-parallel-size 2
```

### Quando Funziona lo Speculative Decoding

```
FUNZIONA BENE:
- Generazione di codice (molto deterministica)
- Testo con pattern ripetitivi
- Task dove il draft model è "abbastanza buono"
- Output lunghi (amortizza l'overhead)

FUNZIONA MALE:
- Creatività alta (il draft rifiutato spesso)
- Lingue per cui il draft model è peggio
- Output corti (overhead > beneficio)
- Latenza alta del draft stesso
```

## 7. Quantizzazione per Serving

| Formato | Precision | VRAM (8B) | Tokens/s | Qualità | Consigliato |
|---------|-----------|-----------|----------|---------|-------------|
| FP32 | 32-bit | ~32 GB | Baseline | Perfetta | No (sprecone) |
| BF16/FP16 | 16-bit | ~16 GB | 1× | Quasi perfetta | Si (default) |
| FP8 (W8A8) | 8-bit weights+act | ~8 GB | 1.5-2× | Ottima | H100+ |
| INT8 | 8-bit | ~8 GB | 1.3× | Buona | Si |
| GPTQ | 4-bit | ~5 GB | 1.2× | Buona | Si |
| AWQ | 4-bit | ~5 GB | 1.3× | Molto buona | Si (migliore di GPTQ) |

```bash
# FP8 su H100 con vLLM
vllm serve meta-llama/Llama-3.1-8B-Instruct \
    --quantization fp8 \
    --dtype float16

# AWQ
vllm serve casperhansen/llama-3-8b-instruct-awq \
    --quantization awq \
    --dtype auto

# GPTQ
vllm serve TheBloke/Llama-3.1-8B-Instruct-GPTQ \
    --quantization gptq \
    --dtype auto
```

## 8. Autoscaling in Kubernetes

### HPA con Custom Metrics GPU

```yaml
# hpa-vllm.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vllm-hpa
  namespace: ai-serving
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-server
  minReplicas: 1
  maxReplicas: 8
  metrics:
    - type: External
      external:
        metric:
          name: vllm_queue_depth  # metrica custom da Prometheus
          selector:
            matchLabels:
              app: vllm
        target:
          type: AverageValue
          averageValue: "10"  # scala quando coda > 10 request per replica
    - type: External
      external:
        metric:
          name: nvidia_gpu_utilization
        target:
          type: AverageValue
          averageValue: "70"  # scala quando GPU > 70% utilizzo
```

```yaml
# deployment vLLM con resource limits GPU
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1         # porta un nuovo pod prima di terminare il vecchio
      maxUnavailable: 0   # zero downtime
  template:
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.6.0
          args:
            - --model=meta-llama/Llama-3.1-8B-Instruct
            - --tensor-parallel-size=1
            - --dtype=bfloat16
            - --max-model-len=32768
            - --disable-log-requests
            - --uvicorn-log-level=warning
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: 32Gi
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 120  # modello lento a caricarsi
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 180
            failureThreshold: 3
```

### KEDA per Autoscaling Avanzato

```yaml
# KEDA ScaledObject per autoscaling basato su Prometheus
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-scaledobject
  namespace: ai-serving
spec:
  scaleTargetRef:
    name: vllm-server
  minReplicaCount: 1
  maxReplicaCount: 10
  cooldownPeriod: 300   # aspetta 5 minuti prima di scale-down
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring.svc:9090
        metricName: vllm_requests_in_flight
        threshold: "20"  # max 20 request in-flight per replica
        query: sum(vllm_requests_in_flight{app="vllm"}) / count(up{app="vllm"})
```

## 9. Monitoring e SLA

### Metriche Prometheus da vLLM

```yaml
# vLLM espone metriche Prometheus su /metrics
# Principali:

# Throughput
vllm:num_requests_running         # request attualmente in inferenza
vllm:num_requests_waiting         # request in coda
vllm:prompt_tokens_total          # token di input processati totale
vllm:generation_tokens_total      # token di output generati totale
vllm:request_success_total        # request completate con successo

# Latenza
vllm:time_to_first_token_seconds  # TTFT (histogram)
vllm:time_per_output_token_seconds # ITL (histogram)
vllm:e2e_request_latency_seconds  # latenza end-to-end (histogram)

# Risorse
vllm:gpu_cache_usage_perc         # % KV cache usata
vllm:cpu_cache_usage_perc         # % CPU cache (swap)
```

```yaml
# Grafana dashboard alert
- alert: HighVLLMQueueDepth
  expr: vllm_requests_waiting > 50
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Alta coda vLLM ({{ $value }} request in attesa)"
    description: "Considerare scale-out del deployment vLLM"

- alert: HighTTFT
  expr: histogram_quantile(0.95, vllm_time_to_first_token_seconds_bucket) > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "TTFT p95 alto: {{ $value }}s"
```

### SLA Tipici per LLM Serving

| SLA | Target | Trigger Allarme |
|-----|--------|-----------------|
| TTFT p50 | < 300ms | > 500ms |
| TTFT p95 | < 1.5s | > 2s |
| TTFT p99 | < 3s | > 5s |
| ITL p95 | < 100ms | > 200ms |
| Error rate | < 0.1% | > 1% |
| GPU Util | > 60% | < 30% (spreco), > 95% (saturo) |

## Best Practices

- **vLLM in produzione, Ollama per sviluppo**: vLLM offre 5-10× il throughput di Ollama grazie a PagedAttention e continuous batching.
- **Speculative decoding per output lunghi**: particolarmente efficace per code generation. Aumenta il throughput del 2-3× senza modificare la qualità.
- **--gpu-memory-utilization 0.85-0.90**: lascia il 10-15% di VRAM libera per picchi di KV cache. 0.95 porta a OOM sotto carico.
- **Readiness probe con delay lungo**: i modelli impiegano 30-120 secondi per caricarsi. Non troppo breve o il pod viene killato prima di essere pronto.
- **Separa le GPU per tenant diversi**: non usare la stessa istanza vLLM per workload di produzione e di test — possono competere per la VRAM.
- **Monitora queue depth come segnale di autoscaling**: la coda di vLLM è il segnale più diretto di saturazione. HPA su queue_depth > soglia.
- **AWQ > GPTQ per qualità**: a parità di compressione (4-bit), AWQ preserva meglio la qualità del modello originale.

## Riferimenti

- [vLLM Documentation](https://docs.vllm.ai/) — Guida completa vLLM
- [vLLM GitHub](https://github.com/vllm-project/vllm) — Source e issue
- [TGI Documentation](https://huggingface.co/docs/text-generation-inference) — HuggingFace TGI
- [PagedAttention Paper (Kwon et al., 2023)](https://arxiv.org/abs/2309.06180) — Paper originale vLLM/PagedAttention
- [Speculative Decoding Paper (Leviathan et al., 2022)](https://arxiv.org/abs/2211.17192) — Paper originale
- [NVIDIA Triton Inference Server](https://developer.nvidia.com/nvidia-triton-inference-server) — Enterprise serving
