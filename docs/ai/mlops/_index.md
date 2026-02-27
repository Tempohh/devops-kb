---
title: "MLOps — Operare LLM in Produzione"
slug: mlops-ai
category: ai
tags: [mlops, model-serving, monitoring, infrastructure, gpu]
search_keywords: [MLOps, ML in produzione, model serving LLM, GPU infrastructure, NVIDIA GPU, vLLM, model monitoring, data drift, experiment tracking, MLflow, model registry, Kubernetes GPU, inference infrastructure, LLM monitoring, cost LLM production]
parent: ai/_index
related: [ai/training/_index, ai/modelli/modelli-open-source, ai/mlops/model-serving, ai/mlops/infrastruttura-gpu, ai/mlops/pipeline-ml]
official_docs: https://docs.vllm.ai/
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# MLOps — Operare LLM in Produzione

## Panoramica

MLOps (Machine Learning Operations) applica i principi DevOps al ciclo di vita dei modelli ML e LLM: automazione, monitoring, reproducibilità, e continuous delivery. Operare un LLM in produzione è significativamente più complesso di deployare un'applicazione web tradizionale: i modelli sono artefatti grandi e stateful, richiedono hardware specializzato (GPU), presentano sfide uniche di latency (prefill vs decode), e producono output non deterministici che richiedono monitoring qualitativo.

Le sfide aggiuntive rispetto al DevOps classico:
- **Data versioning**: i modelli dipendono dai dati di training, che cambiano
- **Model versioning**: un modello è un artefatto di 10-500+ GB
- **Drift**: il comportamento del modello può degradare nel tempo (data drift, concept drift)
- **GPU dependency**: ogni macchina richiede GPU NVIDIA con driver CUDA specifici
- **Batching e throughput**: la produttività dipende dal batching, non solo dalla latenza singola
- **Cost**: i costi GPU sono ordini di grandezza superiori al compute CPU

## MLOps Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                 │
│  Data Storage + Feature Store + Data Versioning (DVC)          │
├─────────────────────────────────────────────────────────────────┤
│                    EXPERIMENT LAYER                             │
│  Training (PyTorch + HuggingFace) + Experiment Tracking (W&B)  │
├─────────────────────────────────────────────────────────────────┤
│                     MODEL LAYER                                 │
│  Model Registry (HuggingFace Hub / MLflow) + Evaluation        │
├─────────────────────────────────────────────────────────────────┤
│                     SERVING LAYER                               │
│  vLLM / TGI + Kubernetes + GPU Nodes + Load Balancer           │
├─────────────────────────────────────────────────────────────────┤
│                   MONITORING LAYER                              │
│  Infra: Prometheus/Grafana | Quality: LangFuse/Helicone        │
└─────────────────────────────────────────────────────────────────┘
```

## Principi MLOps per LLM

### 1. Reproducibilità

```bash
# Ogni run deve essere riproducibile con:
# - Codice (git commit hash)
# - Dati (DVC hash o dataset version)
# - Modello (HuggingFace model ID + revision)
# - Configurazione (hyperparameter in config file)
# - Environment (Docker image tag)

# Esempio di tracking completo
mlflow.start_run(run_name="llama3-devops-ft-v2")
mlflow.set_tags({
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
    "base_model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "dataset_version": "devops-dataset-v2.1"
})
mlflow.log_params({
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "lora_r": 16,
    "batch_size": 8
})
```

### 2. Model Registry

Il model registry è il sistema di verità per quale modello è in produzione, quali sono in staging, e quali sono archiviati.

```
Ciclo di vita modello:
Training → Validation → Registered → Staging → Production → Archived

Transizioni:
- Training → Registered: il modello passa le metriche di eval minime
- Registered → Staging: review umana, A/B test su traffico limitato
- Staging → Production: canary deployment, zero-downtime
- Production → Archived: sostituito da versione più recente
```

### 3. Continuous Evaluation

```python
# Esegui evals automaticamente su ogni candidato modello
# Prima di promuovere a produzione

def can_promote_to_production(model_id: str, eval_results: dict) -> bool:
    MINIMUM_THRESHOLDS = {
        "pass_rate": 0.85,           # 85% dei test devono passare
        "faithfulness": 0.80,        # RAG faithfulness
        "p99_latency_ms": 3000,      # latenza p99 < 3 secondi
        "tokens_per_second": 20      # throughput minimo
    }

    for metric, threshold in MINIMUM_THRESHOLDS.items():
        value = eval_results.get(metric)
        if value is None:
            return False
        if metric == "p99_latency_ms":
            if value > threshold:  # latenza: più basso è meglio
                print(f"FAIL {metric}: {value} > {threshold}")
                return False
        else:
            if value < threshold:  # altre metriche: più alto è meglio
                print(f"FAIL {metric}: {value} < {threshold}")
                return False

    return True
```

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Infrastruttura GPU**

    ---

    GPU lineup (A100, H100, H200). VRAM planning. Multi-GPU setup. Kubernetes con GPU. Cloud vs on-premise.

    [:octicons-arrow-right-24: Infrastruttura GPU](infrastruttura-gpu.md)

-   **Model Serving — vLLM e TGI**

    ---

    vLLM con PagedAttention e continuous batching. TGI, Ollama, Triton. Speculative decoding. Autoscaling. SLA e monitoring.

    [:octicons-arrow-right-24: Model Serving](model-serving.md)

-   **Pipeline ML e MLOps Tooling**

    ---

    MLflow, W&B, DVC, Kubeflow. Experiment tracking, model registry. CI/CD per ML. Data drift detection. LLM monitoring specifico.

    [:octicons-arrow-right-24: Pipeline ML](pipeline-ml.md)

</div>

## Riferimenti

- [vLLM Documentation](https://docs.vllm.ai/) — Serving framework principale
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html) — Experiment tracking e model registry
- [Weights & Biases Documentation](https://docs.wandb.ai/) — MLOps platform
- [NVIDIA CUDA Best Practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/) — Ottimizzazione GPU
