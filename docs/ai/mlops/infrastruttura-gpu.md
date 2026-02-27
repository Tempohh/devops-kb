---
title: "Infrastruttura GPU per LLM"
slug: infrastruttura-gpu
category: ai
tags: [gpu, cuda, nvidia, vram, h100, a100, kubernetes-gpu, inference-hardware]
search_keywords: [GPU per LLM, NVIDIA H100, A100 GPU, VRAM planning, CUDA, tensor parallelism, pipeline parallelism, Kubernetes GPU device plugin, NVLink, NCCL, GPU inference, cloud GPU AWS p4d, Azure ND, GCP A3, GPU time-slicing, GPU MIG, inferenza GPU]
parent: ai/mlops/_index
related: [ai/mlops/_index, ai/mlops/model-serving, ai/fondamentali/deep-learning, ai/modelli/modelli-open-source]
official_docs: https://docs.nvidia.com/cuda/
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Infrastruttura GPU per LLM

## Panoramica

Le GPU sono il substrate computazionale degli LLM. La differenza fondamentale rispetto alle CPU è il parallelismo massiccio: una A100 ha 6912 CUDA core contro i 32-64 core di una CPU top-of-line. Per le operazioni di algebra lineare che dominano i calcoli negli LLM (moltiplicazioni di matrici enormi), questa differenza di parallelismo si traduce in 100-1000× di speedup. Comprendere le GPU, la VRAM, e le strategie di distribuzione multi-GPU è indispensabile per deployare LLM in produzione.

Questo documento copre il lineage hardware NVIDIA per LLM, il calcolo della VRAM necessaria, le strategie multi-GPU, il deployment su Kubernetes, e il confronto cloud vs on-premise.

## 1. GPU NVIDIA per LLM — Lineup

### Data Center GPU (Inference e Training)

| GPU | Architettura | VRAM | Bandwidth | TFLOPs (FP16) | Use Case LLM |
|-----|-------------|------|-----------|---------------|-------------|
| **H200** | Hopper | 141 GB HBM3e | 4.8 TB/s | 989 | Training frontier model, inference 70B+ |
| **H100 SXM5** | Hopper | 80 GB HBM3 | 3.35 TB/s | 989 | Training, inferenza multi-modello |
| **H100 PCIe** | Hopper | 80 GB HBM2e | 2.0 TB/s | 756 | Server standard, meno interconnect |
| **A100 SXM4 80GB** | Ampere | 80 GB HBM2e | 2.0 TB/s | 312 | Training, inferenza modelli grandi |
| **A100 SXM4 40GB** | Ampere | 40 GB HBM2e | 1.6 TB/s | 312 | Training medio, inferenza |
| **L40S** | Ada Lovelace | 48 GB GDDR6 | 864 GB/s | 362 | Inferenza ottimizzata, senza NVLink |
| **L4** | Ada Lovelace | 24 GB GDDR6 | 300 GB/s | 120 | Inferenza modelli piccoli (7-13B) |
| **A10G** | Ampere | 24 GB GDDR6 | 600 GB/s | 125 | Inferenza, AWS G5 instances |

### GPU Consumer (Sviluppo e Small Inference)

| GPU | VRAM | Bandwidth | Use Case LLM |
|-----|------|-----------|-------------|
| **RTX 4090** | 24 GB GDDR6X | 1 TB/s | Dev, QLoRA fine-tuning 7-13B, inferenza |
| **RTX 4080** | 16 GB GDDR6X | 716 GB/s | Dev, inferenza 7B |
| **RTX 3090** | 24 GB GDDR6X | 936 GB/s | Dev, inferenza — più economico del 4090 |
| **RTX 3080 Ti** | 12 GB GDDR6X | 912 GB/s | Inferenza 7B Q4 |

!!! note "Memory Bandwidth > TFLOPS per Inferenza"
    Per l'inferenza LLM, il **memory bandwidth** (velocità di lettura della VRAM) è spesso il collo di bottiglia, non il compute TFLOPS. L'inferenza è *memory-bound*: il bottleneck è quanto velocemente si possono leggere i pesi del modello. Ecco perché la H100 è molto più veloce della A100 per token/secondo nonostante abbiano TFLOPs simili: la H100 ha HBM3 con bandwidth quasi doppia.

### NVIDIA Hopper — Innovazioni Chiave

```
H100 Innovations:
├── HBM3: 3.35 TB/s bandwidth (vs 2.0 TB/s HBM2e di A100)
├── FP8 Tensor Cores: training e inferenza in FP8 (2× throughput vs FP16)
├── Transformer Engine: accelerazione hardware per multi-head attention
├── NVLink 4.0: 900 GB/s tra GPU (vs 600 GB/s NVLink 3.0)
└── DGX H100: 8× H100 con 640 GB VRAM totali e NVLink switch
```

## 2. VRAM Planning

La VRAM è la risorsa più critica e più costosa. Deve contenere:

1. **Model weights**: i parametri del modello
2. **KV Cache**: per ogni request in-flight, durante la generazione
3. **Activations**: valori intermedi durante il forward pass
4. **CUDA overhead**: ~1-2 GB per il runtime CUDA

### Formula Base

```
VRAM_total = weights_size + kv_cache_size + activations + overhead

weights_size (FP16) = num_parameters × 2 bytes
weights_size (FP32) = num_parameters × 4 bytes
weights_size (NF4)  = num_parameters × 0.5 bytes (4-bit)

KV cache (vedi context-window.md per formula dettagliata):
= 2 × num_layers × num_kv_heads × head_dim × max_seq_len × batch_size × 2 bytes (BF16)
```

### Tabella VRAM per Modello

| Modello | Parametri | FP16 Weights | FP8 Weights | NF4 Weights | GPU Fit (FP16) | GPU Fit (NF4) |
|---------|-----------|-------------|------------|------------|----------------|---------------|
| Llama 3.2 3B | 3B | ~6 GB | ~3 GB | ~1.5 GB | 1× L4 | 1× RTX 3080 |
| Llama 3.1 8B | 8B | ~16 GB | ~8 GB | ~4 GB | 1× A100 40GB | 1× RTX 4090 |
| Llama 3.1 13B | 13B | ~26 GB | ~13 GB | ~7 GB | 1× A100 40GB | 1× RTX 4090 |
| Llama 3.1 70B | 70B | ~140 GB | ~70 GB | ~35 GB | 2× A100 80GB | 2× A100 40GB |
| Llama 3.1 405B | 405B | ~810 GB | ~405 GB | ~202 GB | 10× A100 80GB | 3× H100 80GB |
| Mistral 7B | 7B | ~14 GB | ~7 GB | ~3.5 GB | 1× A100 40GB | 1× RTX 4090 |
| Mixtral 8×7B | 46.7B (att: 12.9B) | ~94 GB | ~47 GB | ~23 GB | 2× A100 40GB | 1× A100 40GB |

!!! warning "VRAM + KV Cache"
    La tabella sopra mostra solo la VRAM per i pesi. In produzione, aggiungere 20-40% per KV cache e overhead. Una regola pratica: per inferenza confortevole, servono circa 1.3-1.5× la dimensione dei pesi.

### Calcolo Batch-Aware

```python
def calculate_vram_requirement(
    num_params: int,          # milioni di parametri (es. 8000 per 8B)
    dtype: str = "fp16",      # "fp32", "fp16", "bf16", "nf4", "fp8"
    max_seq_len: int = 4096,
    batch_size: int = 8,
    num_layers: int = 32,
    num_kv_heads: int = 8,
    head_dim: int = 128,
) -> dict:
    """Calcola il requisito VRAM in GB."""
    bytes_per_param = {"fp32": 4, "fp16": 2, "bf16": 2, "fp8": 1, "nf4": 0.5}[dtype]

    weights_gb = (num_params * 1e6 * bytes_per_param) / 1e9

    # KV Cache per tutti i layer e le request nel batch
    kv_cache_bytes = (
        2 *              # K e V
        num_layers *
        num_kv_heads *
        head_dim *
        max_seq_len *
        batch_size *
        2               # BF16 per il compute
    )
    kv_cache_gb = kv_cache_bytes / 1e9

    overhead_gb = 2.0  # CUDA runtime, activations, gradients (inference only)

    total_gb = weights_gb + kv_cache_gb + overhead_gb

    return {
        "weights_gb": round(weights_gb, 1),
        "kv_cache_gb": round(kv_cache_gb, 1),
        "overhead_gb": overhead_gb,
        "total_gb": round(total_gb, 1),
        "recommended_vram_gb": round(total_gb * 1.2, 1)  # 20% buffer
    }

# Esempio: Llama 3.1 8B in FP16 con batch_size=8
result = calculate_vram_requirement(
    num_params=8000,
    dtype="fp16",
    max_seq_len=4096,
    batch_size=8,
    num_layers=32,
    num_kv_heads=8,
    head_dim=128
)
print(result)
# {'weights_gb': 16.0, 'kv_cache_gb': 16.8, 'overhead_gb': 2.0, 'total_gb': 34.8, 'recommended_vram_gb': 41.8}
```

## 3. Multi-GPU Setup

Quando un modello non entra in una singola GPU, servono strategie di distribuzione.

### Tensor Parallelism

Divide ogni layer su più GPU in parallelo. I pesi delle matrici di attention e FFN vengono spezzati lungo una dimensione.

```
Tensor Parallelism con 4 GPU su Llama 3.1 70B:
Ogni GPU contiene 1/4 di ogni layer
= 70B × (2 bytes FP16) / 4 = 35 GB per GPU

Vantaggio: ogni GPU processa il batch intero ma su 1/4 del modello
Svantaggio: richiede comunicazione all-reduce sincronizzata per ogni layer (NVLink essenziale)
Librerie: Megatron-LM, vLLM (--tensor-parallel-size), DeepSpeed
```

```bash
# vLLM con tensor parallelism su 4 GPU
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 32768
```

### Pipeline Parallelism

Divide il modello in stadi sequenziali: la prima GPU processa i primi N layer, la seconda i layer successivi, ecc.

```
Pipeline Parallelism con 4 GPU su 80 layer:
GPU 0: layer 0-19
GPU 1: layer 20-39
GPU 2: layer 40-59
GPU 3: layer 60-79

Vantaggio: comunicazione minima (solo tra stadi adiacenti)
Svantaggio: pipeline bubble (GPU 0 aspetta che l'output attraversi tutti gli stadi)
Use case: quando NVLink non è disponibile, multi-nodo
```

### Data Parallelism

Ogni GPU ha una copia completa del modello e processa batch diversi. Solo per training, non per serving.

```python
# PyTorch DistributedDataParallel
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

dist.init_process_group(backend='nccl')  # NCCL = ottimizzato per GPU NVIDIA
local_rank = int(os.environ['LOCAL_RANK'])
model = model.to(f'cuda:{local_rank}')
model = DDP(model, device_ids=[local_rank])
# Ogni processo ha una GPU diversa, i batch vengono distribuiti automaticamente
```

### NCCL e NVLink

```
NCCL (NVIDIA Collective Communications Library):
- All-Reduce, All-Gather, Reduce-Scatter per comunicazione tra GPU
- Usa NVLink se disponibile (900 GB/s su H100 SXM)
- Fallback su PCIe (64 GB/s bidirezionale) o Ethernet (100-400 Gb/s)

NVLink bandwidth:
- H100 SXM5: 900 GB/s bidirezionale (NVLink 4.0)
- A100 SXM4: 600 GB/s bidirezionale (NVLink 3.0)
- RTX 4090: No NVLink (consumer GPU)

PCIe bandwidth:
- PCIe 5.0 x16: 128 GB/s teorico, ~60 GB/s effettivo
- PCIe 4.0 x16: 64 GB/s teorico, ~30 GB/s effettivo
```

## 4. CUDA Basics

```
CUDA Hierarchy:
GPU
└── Streaming Multiprocessors (SM) — es. H100: 132 SM
    └── CUDA Cores (FP32) — es. 128 per SM
        └── Tensor Cores (matrix multiply) — ottimizzati per DL

Thread Hierarchy:
Grid (kernel launch)
└── Block (max 1024 thread, stesso SM)
    └── Warp (32 thread, eseguono in lockstep)
        └── Thread (un CUDA core)
```

```python
import torch

# Verifica disponibilità CUDA e caratteristiche
print(f"CUDA disponibile: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM totale: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
print(f"VRAM disponibile: {torch.cuda.memory_reserved(0) / 1e9:.1f} GB riservata")
print(f"Compute capability: {torch.cuda.get_device_capability(0)}")
# (8, 0) = Ampere (A100), (9, 0) = Hopper (H100)

# Monitora VRAM durante il runtime
print(f"VRAM allocata: {torch.cuda.memory_allocated(0) / 1e9:.2f} GB")
print(f"VRAM riservata (cache): {torch.cuda.memory_reserved(0) / 1e9:.2f} GB")

# Svuota cache
torch.cuda.empty_cache()
```

```bash
# nvidia-smi: monitoring GPU
nvidia-smi                          # status istantaneo
nvidia-smi dmon -s u               # utilization monitoring real-time
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv -l 5               # CSV ogni 5 secondi

# Informazioni compatibilità CUDA
nvidia-smi | grep "CUDA Version"

# nvidia-smi topo: topologia GPU
nvidia-smi topo -m                 # visualizza connettività NVLink/PCIe
```

## 5. Kubernetes con GPU

### Device Plugin NVIDIA

Per schedulare workload GPU su Kubernetes, serve il NVIDIA device plugin che espone le GPU come risorse Kubernetes.

```bash
# Installa il NVIDIA device plugin
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verifica che le GPU siano visibili
kubectl get nodes -o json | jq '.items[].status.allocatable | select(."nvidia.com/gpu")'
```

### Workload con GPU

```yaml
# deployment-vllm.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-server
  namespace: ai-serving
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm
  template:
    metadata:
      labels:
        app: vllm
    spec:
      containers:
        - name: vllm
          image: vllm/vllm-openai:latest
          command:
            - python
            - -m
            - vllm.entrypoints.openai.api_server
            - --model
            - /models/llama-3.1-8b
            - --dtype
            - bfloat16
            - --tensor-parallel-size
            - "1"
            - --max-model-len
            - "32768"
          resources:
            requests:
              nvidia.com/gpu: 1      # richiedi 1 GPU
              memory: 32Gi
              cpu: "4"
            limits:
              nvidia.com/gpu: 1      # limite = 1 GPU
              memory: 48Gi
              cpu: "8"
          volumeMounts:
            - name: model-storage
              mountPath: /models
      volumes:
        - name: model-storage
          persistentVolumeClaim:
            claimName: model-pvc
      # Toleration per nodi GPU dedicati
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      nodeSelector:
        nvidia.com/gpu.product: "NVIDIA-A100-SXM4-80GB"
```

### GPU Time-Slicing (Condivisione GPU)

```yaml
# ConfigMap per time-slicing (NVIDIA GPU Operator)
# Permette di condividere 1 GPU fisica tra più pod
apiVersion: v1
kind: ConfigMap
metadata:
  name: time-slicing-config
  namespace: gpu-operator
data:
  any: |-
    version: v1
    flags:
      migStrategy: none
    sharing:
      timeSlicing:
        resources:
          - name: nvidia.com/gpu
            replicas: 4  # 1 GPU fisica = 4 GPU virtuali (time-shared)
```

### MIG — Multi-Instance GPU

```bash
# H100 e A100 supportano MIG: divide la GPU in istanze fisiche isolate
# Ogni istanza ha la propria VRAM e motori compute dedicati

# Abilita MIG
sudo nvidia-smi -i 0 -mig 1

# Crea istanze MIG (A100 80GB)
# 7× 1g.10gb: 7 istanze da ~10GB ciascuna
# 4× 2g.20gb: 4 istanze da ~20GB ciascuna
# 1× 7g.80gb: 1 istanza full-size
sudo nvidia-smi mig -i 0 -cgi 19,19,19,19 -C  # 4× 2g.20gb

# Verifica istanze create
nvidia-smi -L
# GPU 0: NVIDIA A100-SXM4-80GB (UUID: GPU-xxx)
#   MIG 2g.20gb Device 0: (UUID: MIG-xxx)
#   MIG 2g.20gb Device 1: (UUID: MIG-xxx)
```

## 6. Cloud GPU — Confronto

### AWS GPU Instances

| Instance | GPU | VRAM | GPU Count | CPU | RAM | $/ora (on-demand) |
|----------|-----|------|-----------|-----|-----|------------------|
| g4dn.xlarge | T4 | 16 GB | 1 | 4 vCPU | 16 GB | ~$0.53 |
| g5.xlarge | A10G | 24 GB | 1 | 4 vCPU | 16 GB | ~$1.01 |
| g5.12xlarge | A10G | 4×24 GB | 4 | 48 vCPU | 192 GB | ~$16.29 |
| p3.2xlarge | V100 | 16 GB | 1 | 8 vCPU | 61 GB | ~$3.06 |
| p4d.24xlarge | A100 | 8×40 GB | 8 | 96 vCPU | 1.1 TB | ~$32.77 |
| p4de.24xlarge | A100 | 8×80 GB | 8 | 96 vCPU | 1.1 TB | ~$40.96 |
| p5.48xlarge | H100 | 8×80 GB | 8 | 192 vCPU | 2 TB | ~$98.32 |

### Azure GPU VMs

| VM | GPU | VRAM | Note |
|----|-----|------|------|
| NC4as T4 v3 | T4 | 16 GB | Dev/test |
| NC24ads A100 v4 | A100 | 80 GB | Training/inference |
| ND96amsr A100 v4 | A100 | 8×80 GB | Multi-GPU |
| ND96isr H100 v5 | H100 | 8×80 GB | Frontier |

### GCP GPU VMs

| Instance | GPU | VRAM |
|----------|-----|------|
| a2-highgpu-1g | A100 40GB | 40 GB |
| a2-ultragpu-1g | A100 80GB | 80 GB |
| a3-highgpu-8g | H100 | 8×80 GB |
| a3-megagpu-8g | H100 Mega | 8×141 GB |

### Cloud vs On-Premise

| Aspetto | Cloud | On-Premise |
|---------|-------|------------|
| **Capex** | Zero | Alto (GPU server = $10K-500K) |
| **Opex** | Alto ($/ora) | Medio (datacenter, manutenzione) |
| **Break-even** | < 2.000 ore/mese | > 2.000 ore/mese |
| **Scaling** | Immediato, elastico | Lento (settimane per procurement) |
| **Latenza** | Network overhead | Locale, minimo |
| **Controllo** | Limitato | Totale |
| **Costo Spot** | Fino a -90% (interrompibile) | N/A |

!!! tip "Spot/Preemptible per Training"
    Per workload di training (che possono essere interrotti e ripresi da checkpoint), usa GPU spot/preemptible su cloud: risparmio del 60-90%. Implementa sempre checkpointing robusto ogni 15-30 minuti.

## 7. Ottimizzazione Performance

### Misura il Collo di Bottiglia

```bash
# Profilazione GPU durante inferenza
nvidia-smi dmon -s pucvmet -d 1  # monitoring dettagliato ogni secondo

# NVTX profiling con Nsight Systems
nsys profile \
    --trace=cuda,nvtx,osrt \
    --output=profile.qdrep \
    python serve_model.py

# Pytorch Profiler
import torch.profiler as profiler

with profiler.profile(
    activities=[profiler.ProfilerActivity.CPU, profiler.ProfilerActivity.CUDA],
    record_shapes=True,
    with_flops=True
) as prof:
    output = model(input_ids)

print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=20))
```

### Regole di Ottimizzazione

1. **Usa BF16 invece di FP32**: 2× meno VRAM, 2× più throughput su Ampere+
2. **Flash Attention**: riduce la memoria per l'attention da O(n²) a O(n) — usa sempre
3. **Continuous batching**: non aspettare che un batch si completi prima di aggiungere nuove request (vLLM fa questo)
4. **Compilation**: `torch.compile(model)` per ottimizzazione CUDA graph
5. **Tensor parallelism**: per latenza bassa su single request, distribui il modello su più GPU

## Best Practices

- **Scegli in base al memory bandwidth, non al TFLOPS**: per inferenza, A100 con 2TB/s batte molte GPU "più potenti" in TFLOPS ma con bandwidth inferiore.
- **Monitora VRAM in produzione**: imposta alert quando VRAM supera 85% — rischi OOM sotto picchi di carico.
- **Usa GPU spot per training**: con checkpoint ogni 15-30 minuti, le interruzioni sono tollerabili e si risparmia 60-90%.
- **NVLink è essenziale per tensor parallelism**: senza NVLink, la comunicazione PCIe diventa il bottleneck. Su consumer GPU (no NVLink), usa pipeline parallelism invece.
- **Separa inference da training GPU**: le GPU di training sono costantemente saturate; condividerle con l'inferenza crea picchi imprevedibili.
- **Kubernetes MIG per GPU sharing**: usa MIG su A100/H100 per servire modelli piccoli (7B, 13B) su istanze isolate della stessa GPU fisica.

## Riferimenti

- [NVIDIA CUDA Documentation](https://docs.nvidia.com/cuda/) — Guide e best practice CUDA
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/) — Kubernetes GPU management
- [NVIDIA Nsight Systems](https://developer.nvidia.com/nsight-systems) — GPU profiling
- [vLLM Performance Documentation](https://docs.vllm.ai/en/latest/performance_benchmark.html) — Benchmark e ottimizzazione
- [AWS GPU Instances](https://aws.amazon.com/ec2/instance-types/#Accelerated_Computing) — Instance types GPU
