---
title: "Fine-Tuning — LoRA, QLoRA, RLHF, DPO"
slug: fine-tuning
category: ai
tags: [fine-tuning, lora, qlora, rlhf, dpo, peft, sft]
search_keywords: [LoRA fine-tuning, QLoRA, RLHF, DPO Direct Preference Optimization, PEFT parameter efficient, Unsloth, TRL HuggingFace, SFT supervised fine-tuning, reward model, PPO reinforcement learning, dataset Alpaca, ShareGPT format, NF4 quantization, adapter, instruction tuning, preference dataset]
parent: ai/training/_index
related: [ai/training/_index, ai/training/valutazione, ai/fondamentali/deep-learning, ai/mlops/infrastruttura-gpu, ai/modelli/modelli-open-source]
official_docs: https://huggingface.co/docs/trl/index
status: complete
difficulty: expert
last_updated: 2026-03-28
---

# Fine-Tuning — LoRA, QLoRA, RLHF, DPO

## Panoramica

Il fine-tuning di un LLM adatta un modello pre-addestrato a un task specifico o a un dominio particolare. Esistono diversi approcci con trade-off molto diversi in termini di costo computazionale, qualità, e rischio di "catastrophic forgetting" (perdita delle capacità generali del modello). Il fine-tuning moderno si articola attorno a metodi **parameter-efficient** (LoRA, QLoRA) che modificano solo una piccola frazione dei pesi del modello, e metodi di **allineamento delle preferenze** (RLHF, DPO) per adattare il comportamento del modello alle aspettative umane.

La differenza tra un buon fine-tuning e uno pessimo è quasi sempre nella qualità del dataset, non nell'algoritmo. 100 esempi perfetti battono 100.000 esempi mediocri. La fase di preparazione e cura del dataset richiede il 70-80% del tempo totale.

## 1. Full Fine-Tuning

Il full fine-tuning aggiorna tutti i parametri del modello. Costa enormemente in compute e memoria, richiede dataset grandi, e rischia il catastrophic forgetting.

```
Full Fine-Tuning:
- Tutti i parametri vengono aggiornati (7B → 7 miliardi di gradienti)
- Richede FP16/BF16 weights + optimizer states (Adam: 4× weights) + gradients
- Llama 3.1 8B full FT: ~128 GB VRAM minima
- Raramente necessario: quasi sempre PEFT è sufficiente
```

**Quando usare:** mai in pratica, a meno di avere un dataset di milioni di esempi e accesso a cluster GPU enterprise. Anche Meta e Anthropic usano varianti di PEFT per i propri modelli.

## 2. LoRA — Low-Rank Adaptation

LoRA congela i pesi originali del modello e inserisce matrici di aggiornamento a basso rango (rank) nei layer Transformer. Solo queste matrici piccole vengono addestrate.

### Come Funziona

```
Peso originale W (frozen): d × k  (es. 4096 × 4096 = 16.7M parametri)

LoRA aggiunge:
  A: d × r  (es. 4096 × 16 = 65.5K parametri)
  B: r × k  (es. 16 × 4096 = 65.5K parametri)

Output = W·x + (B·A)·x × (alpha/r)

Parametri addestrati: 2 × d × r = 131K invece di 16.7M
Riduzione: 99.2% dei parametri!
```

| Hyperparametro | Descrizione | Valori Tipici |
|---------------|-------------|---------------|
| `r` (rank) | Dimensione delle matrici LoRA | 4, 8, 16, 32, 64 |
| `alpha` | Scaling factor (alpha/r) | Uguale a r o doppio (es. r=16, alpha=32) |
| `target_modules` | Layer su cui applicare LoRA | q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj, down_proj |
| `dropout` | Dropout nelle matrici LoRA | 0.05-0.1 |

```python
from peft import LoraConfig, get_peft_model, TaskType
from transformers import AutoModelForCausalLM, AutoTokenizer

# Carica il modello base
model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(model_id)

# Configura LoRA
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,                    # rank
    lora_alpha=32,           # scaling = alpha/r = 2.0
    target_modules=[         # layer su cui applicare LoRA
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_dropout=0.05,
    bias="none",
    inference_mode=False
)

# Applica LoRA al modello
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# trainable params: 20,185,088 || all params: 8,051,224,576 || trainable%: 0.2508
```

## 3. QLoRA — LoRA con Quantizzazione 4-bit

QLoRA combina LoRA con la quantizzazione 4-bit del modello base (NF4 = NormalFloat 4-bit). Permette di fare fine-tuning di modelli enormi su GPU consumer.

```
QLoRA = modello base in NF4 (4-bit) + adapter LoRA in BF16

Llama 3.1 8B:
  FP16:   ~16 GB VRAM
  NF4:    ~4.5 GB VRAM → si fa fine-tuning su GPU da 8-12 GB!

Llama 3.1 70B:
  FP16:  ~140 GB VRAM (4-5 A100)
  NF4:   ~40 GB VRAM (1-2 A100 o 2 RTX 4090)
```

```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import torch

# Configurazione quantizzazione 4-bit
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",          # NormalFloat4 — migliore qualità
    bnb_4bit_compute_dtype=torch.bfloat16,  # compute in BF16
    bnb_4bit_use_double_quant=True      # quantizza anche le costanti di quantizzazione
)

# Carica modello in 4-bit
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    quantization_config=bnb_config,
    device_map="auto"
)

# Prepara per training in kbit (gestisce cast FP32 per layer norm)
model = prepare_model_for_kbit_training(model)

# Applica LoRA
lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
model = get_peft_model(model, lora_config)
```

### QLoRA con Unsloth (Consigliato)

Unsloth è una libreria che ottimizza il fine-tuning con patch custom di Triton/CUDA: 2-5× più veloce di vanilla HuggingFace, 50-70% meno VRAM.

```python
# pip install unsloth
from unsloth import FastLanguageModel
import torch

# Carica modello ottimizzato
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Meta-Llama-3.1-8B-Instruct",
    max_seq_length=4096,
    dtype=None,           # auto: BF16 su Ampere+, FP16 su Volta
    load_in_4bit=True
)

# Aggiungi LoRA adapter con un singolo comando
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,          # Unsloth ottimizza con dropout=0
    bias="none",
    use_gradient_checkpointing="unsloth",  # 30% meno VRAM
    random_state=42,
)
model.print_trainable_parameters()
```

## 4. Dataset Preparation

### Formati Dataset

**Alpaca Format** (instruction tuning):

```json
[
    {
        "instruction": "Analizza questo manifest Kubernetes e identifica problemi di sicurezza",
        "input": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: myapp\nspec:\n  template:\n    spec:\n      containers:\n      - name: app\n        image: myapp:latest\n        securityContext:\n          runAsRoot: true",
        "output": "PROBLEMI IDENTIFICATI:\n1. **CRITICO** - runAsRoot: true: Il container gira come root. Usa runAsNonRoot: true e specifica runAsUser con UID non-root (es. 1000).\n2. **HIGH** - Nessun SecurityContext a livello pod.\n3. **MEDIUM** - Tag 'latest' per l'immagine: usa tag specifici per reproducibilità."
    }
]
```

**ShareGPT Format** (conversazioni multi-turn):

```json
[
    {
        "conversations": [
            {
                "from": "human",
                "value": "Ho un pod che va in CrashLoopBackOff. Come lo debuggo?"
            },
            {
                "from": "gpt",
                "value": "Per debuggare un pod in CrashLoopBackOff:\n\n1. **Vedi i log**:\n```bash\nkubectl logs <pod-name> --previous\n```\nL'opzione `--previous` mostra i log del container prima del crash.\n\n2. **Descrivi il pod**:\n```bash\nkubectl describe pod <pod-name>\n```\nCerca in 'Events' il motivo del crash.\n\n3. **Casi comuni**:\n- OOMKilled: aumenta i memory limits\n- Errore configurazione: controlla env vars e secrets\n- Probe failure: controlla livenessProbe/readinessProbe"
            }
        ]
    }
]
```

### Qualità dei Dati

```python
# Checklist per la qualità del dataset
quality_criteria = {
    "completezza": "La risposta è completa e non tronca informazioni importanti?",
    "accuratezza": "Le informazioni tecniche sono corrette? (verifica da esperto)",
    "formato": "Il formato è coerente con gli altri esempi del dataset?",
    "lunghezza": "La risposta è appropriatamente lunga (né troppo breve né verbosa)?",
    "specificità": "La risposta è specifica al contesto della domanda?",
    "esempi": "Include esempi pratici/codice dove appropriato?",
    "no_allucinazioni": "Non contiene affermazioni false o inventate?"
}

def filter_dataset(examples: list[dict]) -> list[dict]:
    """Filtra esempi di bassa qualità."""
    filtered = []
    for ex in examples:
        response = ex.get("output", "")

        # Filtra risposte troppo corte
        if len(response) < 100:
            continue

        # Filtra risposte che probabilmente sono allucinazioni
        hallucination_patterns = [
            "non esiste", "inventato", "non posso confermare",
            "come IA non", "come modello AI"
        ]
        if any(p in response.lower() for p in hallucination_patterns):
            continue

        # Filtra duplicati
        filtered.append(ex)

    return list({json.dumps(ex): ex for ex in filtered}.values())  # dedup
```

## 5. Supervised Fine-Tuning (SFT)

Il SFT addestra il modello su coppie (instruction, response) di alta qualità.

```python
from trl import SFTTrainer, SFTConfig
from transformers import TrainingArguments
from datasets import Dataset

# Prepara dataset
def format_alpaca(example: dict) -> dict:
    """Formatta un esempio Alpaca nel formato chat del modello."""
    if example.get("input"):
        text = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Sei un esperto DevOps e SRE.<|eot_id|><|start_header_id|>user<|end_header_id|>
{example['instruction']}

{example['input']}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
{example['output']}<|eot_id|>"""
    else:
        text = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Sei un esperto DevOps e SRE.<|eot_id|><|start_header_id|>user<|end_header_id|>
{example['instruction']}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
{example['output']}<|eot_id|>"""
    return {"text": text}

# Carica e formatta dataset
import json
with open("devops_dataset.json") as f:
    raw_data = json.load(f)

dataset = Dataset.from_list([format_alpaca(ex) for ex in raw_data])
train_val = dataset.train_test_split(test_size=0.1, seed=42)

# Training config
training_args = SFTConfig(
    output_dir="./llama3-devops-ft",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    gradient_accumulation_steps=4,   # effective batch = 2×4 = 8
    warmup_steps=50,
    learning_rate=2e-4,              # LoRA tipicamente usa LR più alto
    bf16=True,
    logging_steps=10,
    evaluation_strategy="steps",
    eval_steps=100,
    save_steps=200,
    save_total_limit=3,
    load_best_model_at_end=True,
    max_seq_length=4096,
    dataset_text_field="text",       # campo del dataset con il testo formattato
    report_to="wandb",               # traccia su W&B
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    args=training_args,
    train_dataset=train_val["train"],
    eval_dataset=train_val["test"],
)

# Training!
trainer.train()
trainer.save_model()
```

## 6. RLHF — Reinforcement Learning from Human Feedback

RLHF è la tecnica usata per allineare i modelli alle preferenze umane (come in ChatGPT e Claude). È complessa da implementare correttamente.

### Step 1: SFT (Supervised Fine-Tuning)

Fase iniziale: fine-tuning su risposte di alta qualità scritte da umani.

### Step 2: Reward Model Training

```python
# Il reward model prende (prompt, risposta) e predice un punteggio di qualità
# Addestrato su dataset di preferenze: ogni esempio ha una risposta "chosen" e una "rejected"

from trl import RewardTrainer, RewardConfig
from datasets import Dataset

# Formato dataset preferenze
preference_data = [
    {
        "prompt": "Come si fa rolling update in K8s?",
        "chosen": "Per fare rolling update: 1) modifica l'immagine in Deployment 2) kubectl set image...",
        "rejected": "Aggiorna il deploy e basta"
    },
    # ...
]

# Il RewardTrainer addestra un modello di classificazione
# con head lineare sopra all'LLM per predire lo score
reward_config = RewardConfig(
    output_dir="./reward_model",
    num_train_epochs=1,
    per_device_train_batch_size=4,
    learning_rate=1e-5,
    bf16=True,
)

reward_trainer = RewardTrainer(
    model=reward_model,     # copia del SFT model con head lineare
    tokenizer=tokenizer,
    args=reward_config,
    train_dataset=preference_dataset,
)
reward_trainer.train()
```

### Step 3: PPO Training

```python
from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead

ppo_config = PPOConfig(
    model_name="./sft_model",
    learning_rate=1e-5,
    batch_size=16,
    mini_batch_size=4,
    gradient_accumulation_steps=4,
    kl_penalty="kl",      # KL divergence penalty
    target_kl=6.0,        # target KL per evitare drift eccessivo
    ratio_threshold=10.0  # clip ratio
)

ppo_trainer = PPOTrainer(
    config=ppo_config,
    model=ppo_model,      # SFT model con value head
    ref_model=ref_model,  # copia frozen del SFT model (per KL penalty)
    tokenizer=tokenizer,
    dataset=prompts_dataset,
)

# Training loop PPO
for batch in ppo_trainer.dataloader:
    queries = batch["input_ids"]

    # Genera risposte con il modello corrente
    responses = ppo_trainer.generate(queries, max_new_tokens=200)

    # Calcola reward dal reward model
    rewards = reward_model(queries, responses)

    # Step PPO
    stats = ppo_trainer.step(queries, responses, rewards)
    ppo_trainer.log_stats(stats, batch, rewards)
```

## 7. DPO — Direct Preference Optimization

DPO elimina la necessità di un reward model separato e di PPO, rendendo l'allineamento alle preferenze molto più stabile e semplice.

### Come Funziona DPO

DPO ottimizza direttamente la policy del modello su un dataset di preferenze, usando il modello di riferimento (SFT model) come baseline implicita. La loss function DPO:

```
L_DPO(π; π_ref) = -E[(x,y_w,y_l)] [log σ(β log(π(y_w|x)/π_ref(y_w|x)) - β log(π(y_l|x)/π_ref(y_l|x)))]

dove:
  y_w = risposta "chosen" (preferita dall'umano)
  y_l = risposta "rejected" (non preferita)
  β = temperatura (tipicamente 0.1-0.5)
  π_ref = SFT model (frozen)
```

```python
from trl import DPOTrainer, DPOConfig

# Dataset formato DPO
dpo_dataset = [
    {
        "prompt": "Come scrivo un Dockerfile sicuro per un'app Node.js?",
        "chosen": """FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
USER node
EXPOSE 3000
CMD ["node", "server.js"]

Note di sicurezza:
- Alpine riduce attack surface
- npm ci invece di npm install per reproducibilità
- USER node: non gira come root
- Stage multi-stage non necessario se solo production""",
        "rejected": """FROM node:latest
WORKDIR /app
COPY . .
RUN npm install
CMD ["npm", "start"]"""
    }
]

dpo_config = DPOConfig(
    output_dir="./dpo_model",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    learning_rate=5e-7,    # DPO usa LR più basso di SFT
    beta=0.1,              # temperatura KL — più alto = più conservativo
    bf16=True,
    max_prompt_length=1024,
    max_length=2048,
)

dpo_trainer = DPOTrainer(
    model=model,           # SFT model da allineare
    ref_model=ref_model,   # copia frozen del SFT model
    args=dpo_config,
    train_dataset=Dataset.from_list(dpo_dataset),
    tokenizer=tokenizer,
)

dpo_trainer.train()
```

### DPO vs RLHF

| Aspetto | RLHF (PPO) | DPO |
|---------|-----------|-----|
| Complessità | Alta (2 modelli + reward model) | Bassa (2 modelli) |
| Stabilità | Instabile, sensibile agli hyperparameter | Stabile |
| Qualità | Leggermente superiore | Molto simile |
| Compute | 3× più del SFT | 2× del SFT |
| Dataset | Prompts + preferenze | Solo preferenze |
| **Consiglio** | Per ricerca avanzata | **Per pratica: usa DPO** |

## 8. Merge e Deployment

```python
# Dopo il training, merge adapter LoRA nei pesi del modello base
from peft import AutoPeftModelForCausalLM

# Carica il modello con adapter
model = AutoPeftModelForCausalLM.from_pretrained(
    "./llama3-devops-ft",
    device_map="auto",
    torch_dtype=torch.bfloat16
)

# Merge adapter in base model (pesi finali combinati)
merged_model = model.merge_and_unload()

# Salva modello merged (completo, senza adapter separato)
merged_model.save_pretrained("./llama3-devops-merged")
tokenizer.save_pretrained("./llama3-devops-merged")

# Upload su HuggingFace Hub
merged_model.push_to_hub("myorg/llama3-devops-expert")
tokenizer.push_to_hub("myorg/llama3-devops-expert")
```

```bash
# Quantizza per deployment
python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained('./llama3-devops-merged')
# Poi usa llama.cpp per quantizzare in GGUF:
"

# Conversione in GGUF con llama.cpp
python convert_hf_to_gguf.py ./llama3-devops-merged --outfile llama3-devops.gguf

# Quantizza in Q4_K_M
./llama-quantize llama3-devops.gguf llama3-devops-q4km.gguf Q4_K_M
```

## VRAM Required per Fine-Tuning

| Modello | Metodo | VRAM Min | VRAM Comodo | GPU Consigliata |
|---------|--------|----------|-------------|-----------------|
| Llama 3.1 8B | QLoRA (NF4) | 8 GB | 12-16 GB | RTX 3090/4090, A10 |
| Llama 3.1 8B | LoRA (BF16) | 24 GB | 40 GB | A100 40GB |
| Llama 3.1 70B | QLoRA (NF4) | 40 GB | 2×40 GB | 2× A100 40GB |
| Llama 3.1 70B | LoRA (BF16) | 160 GB | 4×80 GB | 4× A100 80GB |
| Llama 3.1 405B | QLoRA (NF4) | 200 GB | 4×80 GB | 4× H100 80GB |

## Best Practices

- **Qualità prima della quantità**: 500 esempi perfetti > 50.000 mediocri. Verifica ogni esempio manualmente o usa LLM-as-judge.
- **Valuta su eval set separato**: tieni il 10-15% del dataset come validation set. Stoppa prima dell'overfitting (eval loss che risale).
- **Learning rate scheduling**: usa warmup + cosine decay. Il LR per LoRA (1e-4 a 3e-4) è più alto del full fine-tuning (1e-5).
- **Checkpoint frequenti**: salva ogni 100-200 step. Se il training va storto, non perdere tutto.
- **W&B o MLflow per tracking**: traccia loss, learning rate, eval metrics in tempo reale.
- **Testa il modello fine-tuned con un eval set**: confronta le performance sul tuo task specifico contro il base model.
- **Non dimenticare di valutare la regressione**: il fine-tuning su un task specifico può degradare le capacità generali. Testa su MMLU o task generali dopo il fine-tuning.

## Troubleshooting

### Scenario 1 — CUDA Out of Memory durante il training

**Sintomo:** `RuntimeError: CUDA out of memory` dopo pochi step, o subito all'avvio del training.

**Causa:** Batch size, sequence length o rank LoRA troppo alti per la VRAM disponibile.

**Soluzione:** Ridurre progressivamente il consumo di memoria con le seguenti leve, in ordine di impatto:

```python
# Leva 1: riduci batch size + aumenta gradient accumulation (mantieni effective batch)
per_device_train_batch_size=1,         # da 2 a 1
gradient_accumulation_steps=8,         # da 4 a 8 (effective batch invariato)

# Leva 2: riduci max_seq_length
max_seq_length=2048,                   # da 4096 a 2048

# Leva 3: riduci rank LoRA (meno parametri addestrabili)
r=8,                                   # da 16 a 8

# Leva 4: abilita gradient checkpointing (30-40% meno VRAM, ~20% più lento)
use_gradient_checkpointing="unsloth",  # con Unsloth
# oppure:
model.gradient_checkpointing_enable()  # con HuggingFace vanilla

# Leva 5: passa da LoRA BF16 a QLoRA NF4
load_in_4bit=True                      # quantizzazione del base model
```

### Scenario 2 — Training loss scende ma il modello produce output di bassa qualità

**Sintomo:** La training loss cala regolarmente ma il modello fine-tuned risponde peggio del base model, oppure ripete pattern fissi invece di rispondere al contenuto della domanda.

**Causa 1:** Overfitting — il modello memorizza il dataset invece di generalizzare. Eval loss risale mentre training loss scende.
**Causa 2:** Formato del prompt non coerente tra training e inference.
**Causa 3:** Dataset troppo piccolo o con poca varietà.

**Soluzione:**

```python
# Verifica eval loss in W&B o nei log
# Se eval loss risale → early stopping
training_args = SFTConfig(
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    greater_is_better=False,
    num_train_epochs=3,          # riduci epochs se overfitting rapido
    eval_steps=50,               # eval più frequente
)

# Verifica che il prompt template sia identico in training e inference
# Errore comune: training usa <|begin_of_text|> ma inference no
# Usa sempre il tokenizer.apply_chat_template()
messages = [{"role": "user", "content": "domanda"}]
prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
```

### Scenario 3 — DPO training instabile (loss NaN o divergenza)

**Sintomo:** La DPO loss diventa NaN dopo alcune centinaia di step, oppure il modello collassa producendo sempre la stessa risposta.

**Causa:** Beta troppo basso (il modello si allontana troppo dal reference), oppure il dataset di preferenze ha `chosen` e `rejected` troppo simili tra loro.

**Soluzione:**

```python
# Aumenta beta per penalizzare di più la divergenza dal ref model
dpo_config = DPOConfig(
    beta=0.3,                  # da 0.1 a 0.3 (più conservativo)
    max_prompt_length=512,     # riduci se i prompt sono molto lunghi
    max_length=1024,
    loss_type="sigmoid",       # default, più stabile di "hinge"
)

# Verifica qualità del dataset: chosen e rejected devono essere chiaramente diversi
# Scarta coppie dove la differenza è minima (es. solo punteggiatura)
def filter_preference_pairs(dataset):
    return [ex for ex in dataset
            if len(ex["chosen"]) > 50
            and len(ex["rejected"]) > 20
            and ex["chosen"] != ex["rejected"]]
```

### Scenario 4 — Merge dell'adapter LoRA produce artefatti o qualità degradata

**Sintomo:** Dopo `merge_and_unload()`, il modello merged produce output molto peggiori del modello con adapter caricato separatamente.

**Causa:** Il merge viene eseguito su un modello caricato in 4-bit (QLoRA). Il merge richiede pesi in FP16/BF16.

**Soluzione:** Ricaricare il base model in BF16 prima del merge.

```bash
# Ricarica il base model in BF16 (non quantizzato) per il merge
```

```python
from peft import AutoPeftModelForCausalLM
import torch

# SBAGLIATO: merge su modello 4-bit → artefatti
# model = AutoPeftModelForCausalLM.from_pretrained("./ft", load_in_4bit=True)

# CORRETTO: carica in BF16 per merge pulito
model = AutoPeftModelForCausalLM.from_pretrained(
    "./llama3-devops-ft",
    device_map="auto",
    torch_dtype=torch.bfloat16,
    # NON specificare load_in_4bit=True qui
)

merged_model = model.merge_and_unload()
merged_model.save_pretrained("./llama3-devops-merged", safe_serialization=True)
```

## Riferimenti

- [HuggingFace TRL](https://huggingface.co/docs/trl/) — SFT, PPO, DPO, GRPO trainer
- [Unsloth GitHub](https://github.com/unslothai/unsloth) — Fine-tuning ottimizzato 2-5×
- [LoRA (Hu et al., 2021)](https://arxiv.org/abs/2106.09685) — Paper originale
- [QLoRA (Dettmers et al., 2023)](https://arxiv.org/abs/2305.14314) — 65B su 48GB VRAM
- [DPO (Rafailov et al., 2023)](https://arxiv.org/abs/2305.18290) — Alternativa a RLHF
- [Alpaca Dataset Format](https://github.com/tatsu-lab/stanford_alpaca) — Formato standard SFT
