---
title: "Pipeline ML e MLOps Tooling"
slug: pipeline-ml
category: ai
tags: [mlflow, wandb, dvc, kubeflow, experiment-tracking, model-registry, monitoring]
search_keywords: [MLflow, Weights Biases W&B, DVC Data Version Control, Kubeflow, pipeline ML, experiment tracking, model registry, data versioning, LLM monitoring, LangFuse, Helicone, data drift, concept drift, Evidently, feature store, Feast, CI/CD ML, GitHub Actions ML, MLOps tooling]
parent: ai/mlops/_index
related: [ai/mlops/_index, ai/training/fine-tuning, ai/training/valutazione, ai/mlops/model-serving]
official_docs: https://mlflow.org/docs/latest/
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Pipeline ML e MLOps Tooling

## Panoramica

Una pipeline ML robusta per LLM va ben oltre il semplice training di un modello: include versioning dei dati, tracking degli esperimenti, valutazione sistematica, deployment automatico, e monitoring continuo in produzione. La maturità MLOps di un'organizzazione si misura da quanto questo ciclo è automatizzato e reproducibile. Un team mature può rilasciare una nuova versione del modello in produzione in modo sicuro e rollbackabile, proprio come per il software tradizionale.

Questo documento copre i tool principali per ogni fase del ciclo di vita ML: experiment tracking (MLflow, W&B), data versioning (DVC), pipeline orchestration (Kubeflow), e monitoring specifico per LLM (LangFuse, Helicone).

## 1. Experiment Tracking

L'experiment tracking registra sistematicamente ogni run di training: parametri, metriche, artefatti (modelli, grafici), e il codice. Senza tracking, è impossibile reproducire un esperimento passato o capire perché un modello sia migliore di un altro.

### MLflow

```python
import mlflow
import mlflow.pytorch
from transformers import TrainerCallback

# Inizializzazione
mlflow.set_tracking_uri("http://mlflow-server:5000")  # server remoto
# oppure: mlflow.set_tracking_uri("./mlruns")  # locale
mlflow.set_experiment("llama3-devops-finetuning")

# Run completo
with mlflow.start_run(run_name="qlora-r16-epoch3") as run:
    # Log parametri
    mlflow.log_params({
        "base_model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "lora_r": 16,
        "lora_alpha": 32,
        "learning_rate": 2e-4,
        "num_epochs": 3,
        "batch_size": 8,
        "gradient_accumulation_steps": 4,
        "dataset_version": "devops-v2.1",
        "quantization": "nf4"
    })

    # Log metriche durante il training
    for epoch in range(3):
        train_loss, val_loss = train_epoch(epoch)
        mlflow.log_metrics({
            "train_loss": train_loss,
            "val_loss": val_loss,
            "learning_rate": scheduler.get_last_lr()[0]
        }, step=epoch)

    # Log artefatti
    mlflow.log_artifact("./training_data/dataset_stats.json")
    mlflow.pytorch.log_model(model, "model")

    # Log tags per filtro
    mlflow.set_tags({
        "gpu": "A100-80GB",
        "git_commit": get_git_commit(),
        "status": "completed"
    })

print(f"Run ID: {run.info.run_id}")
```

### Callback MLflow per HuggingFace Trainer

```python
from transformers import TrainerCallback
import mlflow

class MLflowCallback(TrainerCallback):
    def __init__(self):
        self.run = None

    def on_train_begin(self, args, state, control, **kwargs):
        self.run = mlflow.start_run(run_name=f"run-{state.global_step}")
        mlflow.log_params({
            "learning_rate": args.learning_rate,
            "num_epochs": args.num_train_epochs,
            "batch_size": args.per_device_train_batch_size,
            "warmup_steps": args.warmup_steps
        })

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            mlflow.log_metrics(logs, step=state.global_step)

    def on_train_end(self, args, state, control, **kwargs):
        mlflow.end_run()

# Aggiungi al Trainer
trainer = SFTTrainer(
    ...,
    callbacks=[MLflowCallback()]
)
```

### MLflow Model Registry

```python
# Registra il modello nel registry dopo la valutazione
result = mlflow.register_model(
    model_uri=f"runs:/{run_id}/model",
    name="llama3-devops-expert"
)
print(f"Model version: {result.version}")

# Transizioni di stage
client = mlflow.tracking.MlflowClient()

# Staging dopo validazione iniziale
client.transition_model_version_stage(
    name="llama3-devops-expert",
    version=result.version,
    stage="Staging",
    archive_existing_versions=False
)

# Production dopo A/B test
client.transition_model_version_stage(
    name="llama3-devops-expert",
    version=result.version,
    stage="Production",
    archive_existing_versions=True  # archivia la versione precedente
)

# Carica da registry
model = mlflow.pyfunc.load_model(
    model_uri="models:/llama3-devops-expert/Production"
)
```

### Weights & Biases (W&B)

W&B è più ricco di funzionalità di MLflow (visualizzazioni, collaboration) ma è un servizio SaaS a pagamento per team grandi.

```python
import wandb
from transformers import TrainerCallback

# Inizializzazione
wandb.init(
    project="llama3-devops-finetuning",
    name="qlora-r16-epoch3",
    config={
        "base_model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "lora_r": 16,
        "learning_rate": 2e-4,
        "num_epochs": 3
    },
    tags=["qlora", "llama3", "devops"]
)

# Log metriche durante il training
wandb.log({
    "train/loss": train_loss,
    "val/loss": val_loss,
    "train/learning_rate": lr,
    "train/epoch": epoch
}, step=global_step)

# Log tabella per analisi qualitativa
table = wandb.Table(columns=["prompt", "completion", "score"])
for prompt, completion, score in eval_samples:
    table.add_data(prompt, completion, score)
wandb.log({"eval_samples": table})

# Salva modello come artifact W&B
artifact = wandb.Artifact("llama3-devops-expert", type="model")
artifact.add_dir("./final_model/")
wandb.log_artifact(artifact)

wandb.finish()
```

```python
# HuggingFace Trainer integra nativamente con W&B
import os
os.environ["WANDB_PROJECT"] = "llama3-devops-finetuning"
os.environ["WANDB_LOG_MODEL"] = "checkpoint"

training_args = SFTConfig(
    ...,
    report_to="wandb"  # abilita integrazione automatica W&B
)
```

## 2. Data Versioning con DVC

DVC (Data Version Control) porta il versioning di Git a file grandi (dataset, modelli), salvando i file su storage esterno (S3, GCS, Azure Blob) e tracciando solo i metadati in Git.

```bash
# Installazione
pip install dvc dvc-s3  # oppure dvc-gcs, dvc-azure

# Inizializzazione in un repo Git esistente
git init
dvc init
git commit -m "Inizializza DVC"

# Configura storage remoto
dvc remote add -d myremote s3://my-bucket/dvc-store
dvc remote modify myremote region us-east-1

# Aggiungi file grandi al tracking DVC
dvc add data/devops_dataset.json
dvc add models/llama3-devops-expert/

# DVC crea file .dvc che viene tracciato da Git
git add data/devops_dataset.json.dvc models/llama3-devops-expert.dvc .gitignore
git commit -m "Aggiungi dataset v1 e modello al tracking DVC"

# Push dei dati su S3
dvc push

# Recupera i dati su una nuova macchina
git clone <repo>
dvc pull  # scarica i file grandi da S3
```

### DVC Pipeline

```yaml
# dvc.yaml — definisce la pipeline ML riproducibile
stages:
  prepare_data:
    cmd: python prepare_dataset.py --input raw_data/ --output processed_data/
    deps:
      - prepare_dataset.py
      - raw_data/
    outs:
      - processed_data/

  train:
    cmd: python train.py --config configs/qlora.yaml
    deps:
      - train.py
      - configs/qlora.yaml
      - processed_data/
    outs:
      - models/checkpoints/
    metrics:
      - metrics/eval_results.json:
          cache: false  # versiona le metriche, non solo il file

  evaluate:
    cmd: python evaluate.py --model models/checkpoints/best/
    deps:
      - evaluate.py
      - models/checkpoints/best/
    metrics:
      - metrics/final_eval.json:
          cache: false
```

```bash
# Esegui pipeline (esegue solo gli stage con dipendenze cambiate)
dvc repro

# Confronta metriche tra versioni
dvc metrics diff HEAD~1  # confronta con il commit precedente
# Path                   Metric    HEAD~1    HEAD      Change
# metrics/eval_results   pass_rate 0.82      0.87      +0.05
```

## 3. Pipeline Orchestration

### Kubeflow Pipelines

Kubeflow Pipelines orchestra workflow ML su Kubernetes con UI visuale, versioning, e scheduling.

```python
import kfp
from kfp import dsl
from kfp.components import func_to_container_op

# Definisci componenti come funzioni Python
@dsl.component(base_image="python:3.11-slim", packages_to_install=["datasets", "transformers"])
def prepare_data(
    raw_data_path: str,
    output_path: kfp.dsl.Output[kfp.dsl.Dataset]
):
    """Prepara il dataset per il training."""
    from datasets import load_dataset
    import json

    dataset = load_dataset("json", data_files=raw_data_path)
    # ... processing
    dataset.save_to_disk(output_path.path)

@dsl.component(
    base_image="ghcr.io/unslothai/unsloth:latest",
    packages_to_install=[]
)
def fine_tune(
    dataset: kfp.dsl.Input[kfp.dsl.Dataset],
    model_output: kfp.dsl.Output[kfp.dsl.Model],
    base_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    lora_r: int = 16,
    num_epochs: int = 3
):
    """Fine-tuning con QLoRA."""
    from unsloth import FastLanguageModel
    # ... training code

@dsl.component
def evaluate_model(
    model: kfp.dsl.Input[kfp.dsl.Model],
    eval_results: kfp.dsl.Output[kfp.dsl.Metrics]
) -> float:
    """Valuta il modello e ritorna il pass_rate."""
    # ... evaluation code
    return pass_rate

# Definisci la pipeline
@dsl.pipeline(
    name="llm-finetuning-pipeline",
    description="Pipeline completa per fine-tuning e evaluation LLM"
)
def llm_pipeline(
    raw_data_uri: str,
    base_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
):
    # Step 1: preparazione dati
    prep_task = prepare_data(raw_data_path=raw_data_uri)

    # Step 2: fine-tuning (richiede GPU)
    train_task = fine_tune(
        dataset=prep_task.outputs['output_path'],
        base_model=base_model
    )
    train_task.set_gpu_limit(1)
    train_task.add_node_selector_constraint("nvidia.com/gpu.product", "NVIDIA-A100-SXM4-80GB")

    # Step 3: evaluation
    eval_task = evaluate_model(model=train_task.outputs['model_output'])

    # Step 4: promuovi a produzione se metriche OK
    with dsl.Condition(eval_task.output >= 0.85, "metriche-ok"):
        promote_task = promote_to_production(model=train_task.outputs['model_output'])

# Compila e carica su Kubeflow
compiler = kfp.compiler.Compiler()
compiler.compile(llm_pipeline, "llm_pipeline.yaml")

client = kfp.Client(host="http://kubeflow.example.com")
experiment = client.create_experiment("llm-experiments")
run = client.run_pipeline(
    experiment.id,
    "llm-finetuning-run-001",
    "llm_pipeline.yaml",
    params={"raw_data_uri": "s3://my-bucket/dataset.json"}
)
```

### Argo Workflows (Alternativa Leggera)

```yaml
# argo-ml-pipeline.yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  name: llm-finetuning
spec:
  entrypoint: ml-pipeline

  templates:
    - name: ml-pipeline
      steps:
        - - name: prepare-data
            template: prepare-data-step
        - - name: train
            template: train-step
            arguments:
              parameters:
                - name: dataset-path
                  value: "{{steps.prepare-data.outputs.parameters.output-path}}"
        - - name: evaluate
            template: evaluate-step
            arguments:
              parameters:
                - name: model-path
                  value: "{{steps.train.outputs.parameters.model-path}}"

    - name: train-step
      inputs:
        parameters:
          - name: dataset-path
      container:
        image: unslothai/unsloth:latest
        command: [python, train.py]
        args:
          - --dataset={{inputs.parameters.dataset-path}}
          - --output=/models/checkpoint
        resources:
          limits:
            nvidia.com/gpu: "1"
            memory: 40Gi
      outputs:
        parameters:
          - name: model-path
            valueFrom:
              path: /tmp/model-path.txt
```

## 4. LLM Monitoring Specifico

Il monitoring degli LLM in produzione richiede due livelli: **metriche infrastrutturali** (latenza, throughput, errori — standard) e **metriche di qualità** (output length, refusal rate, hallucination rate — specifiche degli LLM).

### LangFuse — LLM Observability

```python
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="https://cloud.langfuse.com"  # o self-hosted
)

# Decorator-based tracing
@observe(name="rag-query")
def process_rag_query(user_query: str, user_id: str) -> str:
    # Automatic tracing di input/output
    langfuse_context.update_current_observation(
        user_id=user_id,
        metadata={"query_type": "documentation"}
    )

    # Traccia il retrieval come span separato
    with langfuse_context.span("retrieval") as span:
        docs = retrieve_documents(user_query)
        span.update(
            input=user_query,
            output={"num_docs": len(docs)},
            metadata={"retriever": "qdrant", "k": 5}
        )

    # Traccia la generazione
    response = call_llm(user_query, docs)
    return response

# Score manuale (per RLHF o valutazione)
langfuse.score(
    trace_id="...",
    name="user_feedback",
    value=1,  # 1 = thumbs up, 0 = thumbs down
    comment="Risposta utile e accurata"
)
```

### Helicone

```python
# Helicone: proxy tra l'app e l'API LLM
# Intercetta ogni chiamata e aggiunge monitoring

from anthropic import Anthropic

# Usa Helicone come proxy
client = Anthropic(
    base_url="https://anthropic.helicone.ai",
    default_headers={
        "Helicone-Auth": f"Bearer {HELICONE_API_KEY}",
        "Helicone-User-Id": user_id,      # per analytics per-user
        "Helicone-Session-Id": session_id, # raggruppa request correlate
        "Helicone-Property-environment": "production",
        "Helicone-Property-feature": "code-review"
    }
)

# Tutto il resto è identico — Helicone è trasparente
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Analizza questo codice..."}]
)
```

### Data Drift e Concept Drift

```python
# Evidently: rileva drift nei dati e nelle predizioni
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset

# Confronta distribuzione dei prompt della settimana passata con quella attuale
past_prompts_df = pd.DataFrame({"prompt": get_prompts(start="-2w", end="-1w")})
current_prompts_df = pd.DataFrame({"prompt": get_prompts(start="-1w", end="now")})

# Estrai feature dai prompt (lunghezza, embedding cluster, tipo di query)
past_prompts_df["length"] = past_prompts_df["prompt"].str.len()
current_prompts_df["length"] = current_prompts_df["prompt"].str.len()

column_mapping = ColumnMapping()
report = Report(metrics=[DataDriftPreset(), DataQualityPreset()])
report.run(
    reference_data=past_prompts_df,
    current_data=current_prompts_df,
    column_mapping=column_mapping
)
report.save_html("drift_report.html")

# Se drift rilevato, triggera re-evaluation del modello
if report.as_dict()["metrics"][0]["result"]["dataset_drift"]:
    trigger_model_evaluation_pipeline()
```

### LLM Quality Metrics in Produzione

```python
# Monitoraggio della qualità dell'output senza feedback umano
import anthropic
import statistics

class LLMQualityMonitor:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.metrics_buffer = []

    def record_response(
        self,
        prompt: str,
        response: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int
    ):
        """Registra una risposta e calcola metriche di qualità."""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "output_length": len(response),
            "refusal": self._is_refusal(response),
            "contains_code": "```" in response,
            "has_error_content": self._has_error_content(response),
            "cost_usd": self._calculate_cost(input_tokens, output_tokens)
        }
        self.metrics_buffer.append(metrics)

        # Flush periodicamente su Prometheus/Datadog/CloudWatch
        if len(self.metrics_buffer) >= 100:
            self._flush_metrics()

    def _is_refusal(self, response: str) -> bool:
        """Rileva se il modello ha rifiutato di rispondere."""
        refusal_patterns = [
            "non posso", "non sono in grado", "mi dispiace ma non",
            "i can't", "i'm not able to", "i'm sorry, but"
        ]
        response_lower = response.lower()
        return any(pattern in response_lower for pattern in refusal_patterns)

    def _has_error_content(self, response: str) -> bool:
        """Rileva pattern di errore comuni."""
        error_patterns = [
            "error:", "exception:", "traceback", "undefined is not",
            "null pointer", "segmentation fault"
        ]
        return any(p in response.lower() for p in error_patterns)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Claude 3.5 Sonnet pricing
        return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000

    def _flush_metrics(self):
        """Flush metriche aggregate su Prometheus pushgateway."""
        if not self.metrics_buffer:
            return

        avg_latency = statistics.mean(m["latency_ms"] for m in self.metrics_buffer)
        refusal_rate = sum(m["refusal"] for m in self.metrics_buffer) / len(self.metrics_buffer)
        total_cost = sum(m["cost_usd"] for m in self.metrics_buffer)

        # Pushgateway Prometheus
        push_metrics_to_prometheus({
            "llm_avg_latency_ms": avg_latency,
            "llm_refusal_rate": refusal_rate,
            "llm_total_cost_usd": total_cost,
            "llm_total_requests": len(self.metrics_buffer)
        })

        self.metrics_buffer = []
```

## 5. CI/CD per ML

```yaml
# .github/workflows/ml-ci-cd.yml
name: ML CI/CD Pipeline

on:
  push:
    branches: [main]
    paths:
      - 'training/**'
      - 'prompts/**'
      - 'data/**'

jobs:
  run-evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run prompt evals (light)
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          pip install anthropic promptfoo
          promptfoo eval --ci --output results/eval.json
      - name: Check regression
        run: python scripts/check_eval_regression.py --threshold 0.03

  trigger-training:
    needs: run-evals
    if: github.ref == 'refs/heads/main' && needs.run-evals.result == 'success'
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Kubeflow Pipeline
        env:
          KUBEFLOW_HOST: ${{ secrets.KUBEFLOW_HOST }}
          KUBEFLOW_TOKEN: ${{ secrets.KUBEFLOW_TOKEN }}
        run: |
          python scripts/trigger_training_pipeline.py \
            --dataset-version $(git rev-parse HEAD) \
            --config configs/production.yaml

  deploy-staging:
    needs: trigger-training
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Wait for training completion
        run: python scripts/wait_for_pipeline.py --timeout 7200
      - name: Run full eval suite on new model
        run: python scripts/run_full_evals.py --model staging
      - name: Deploy to staging
        if: steps.eval.outputs.pass_rate >= 0.85
        run: |
          kubectl set image deployment/vllm-server \
            vllm=registry.example.com/models/llama3-devops:${GITHUB_SHA}
          kubectl rollout status deployment/vllm-server

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production  # richiede approvazione manuale
    steps:
      - name: Canary deploy (10% traffico)
        run: kubectl apply -f k8s/canary-ingress.yaml
      - name: Monitor canary per 30 minuti
        run: python scripts/monitor_canary.py --duration 1800 --threshold 0.01
      - name: Full rollout
        run: |
          kubectl apply -f k8s/production-ingress.yaml
          kubectl rollout status deployment/vllm-server-production
```

## 6. Prompt Injection Detection

```python
# Rileva prompt injection in produzione
import re
from anthropic import Anthropic

client = Anthropic()

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions?",
    r"(?i)disregard\s+(?:all\s+)?(?:your\s+)?(?:previous|prior)",
    r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)",
    r"(?i)(?:act|pretend|behave)\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:a\s+)?(?:different|new|another|unrestricted)",
    r"(?i)DAN\s+mode",
    r"(?i)jailbreak",
    r"(?i)override\s+(?:your\s+)?(?:safety|guidelines|restrictions)",
]

def detect_injection(user_input: str) -> dict:
    """Rileva potenziali prompt injection."""
    detections = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, user_input):
            detections.append(pattern)

    # Usa anche LLM-as-judge per casi sofisticati
    if len(user_input) > 500 and not detections:
        # Controlla solo input lunghi con il LLM per efficienza
        judge_response = client.messages.create(
            model="claude-3-5-haiku-20241022",  # haiku per economia
            max_tokens=100,
            system="Sei un sistema di sicurezza. Analizza l'input e rispondi SOLO con JSON: {\"injection\": true/false}",
            messages=[{"role": "user", "content": f"Input da analizzare: {user_input[:1000]}"}]
        )
        try:
            import json
            result = json.loads(judge_response.content[0].text)
            if result.get("injection"):
                detections.append("llm-judge-detection")
        except:
            pass

    return {
        "is_injection": len(detections) > 0,
        "patterns_detected": detections,
        "action": "block" if detections else "allow"
    }

# Middleware per FastAPI
from fastapi import HTTPException, Request

async def injection_detection_middleware(request: Request, call_next):
    if request.method == "POST":
        body = await request.body()
        # Analizza il body JSON
        try:
            import json
            data = json.loads(body)
            user_message = data.get("messages", [{}])[-1].get("content", "")
            detection = detect_injection(user_message)
            if detection["is_injection"]:
                # Log l'evento
                log_security_event("prompt_injection", user_message, detection)
                raise HTTPException(status_code=400, detail="Richiesta non consentita")
        except (json.JSONDecodeError, KeyError):
            pass

    return await call_next(request)
```

## Best Practices

- **Traccia sempre l'esperimento**: ogni run di training deve essere registrato con parametri, metriche, e artefatti. Non eseguire training senza experiment tracking — non potrai reproducirlo.
- **DVC per ogni dato grande**: dataset, modelli, e artefatti grandi non vanno in Git. DVC + S3 è il pattern standard.
- **Model registry con stage transitions**: non deployare direttamente da CI/CD senza passare per un registry con stage formali (staging → production). Il registry è la fonte di verità.
- **Evals automatici in CI/CD**: ogni modifica a prompt, codice di training, o dataset deve triggare automaticamente gli evals. Una regressione non rilevata in CI è un bug in produzione.
- **LLM-specific monitoring**: le metriche infrastrutturali (latenza, errori) non bastano. Monitora refusal rate, output quality, cost per query, e prompt injection attempt rate.
- **Drift detection proattiva**: non aspettare che gli utenti si lamentino per accorgerti del drift. Implementa drift detection automatica che triggera re-evaluation.
- **Canary deployment per ogni cambio modello**: ogni nuovo modello in produzione va rilasciato prima al 5-10% del traffico, monitorato, e poi gradualmente espanso.

## Riferimenti

- [MLflow Documentation](https://mlflow.org/docs/latest/) — Experiment tracking e model registry
- [Weights & Biases](https://docs.wandb.ai/) — MLOps platform feature-rich
- [DVC Documentation](https://dvc.org/doc) — Data Version Control
- [Kubeflow Pipelines](https://www.kubeflow.org/docs/components/pipelines/) — ML workflow su Kubernetes
- [LangFuse](https://langfuse.com/docs) — LLM observability open source
- [Evidently](https://docs.evidentlyai.com/) — Data e model drift detection
- [Helicone](https://docs.helicone.ai/) — LLM proxy con monitoring integrato
