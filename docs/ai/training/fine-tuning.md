---
title: "Fine-Tuning — LoRA, QLoRA, RLHF, DPO"
slug: fine-tuning
category: ai
tags: [fine-tuning, lora, qlora, rlhf, dpo, peft, sft]
search_keywords: [GRPO, RLVR, LoRA fine-tuning, QLoRA, RLHF, DPO Direct Preference Optimization, PEFT parameter efficient, Unsloth, TRL HuggingFace, SFT supervised fine-tuning, reward model, PPO reinforcement learning, dataset Alpaca, ShareGPT format, NF4 quantization, adapter, instruction tuning, preference dataset]
parent: ai/training/_index
related: [ai/training/_index, ai/training/valutazione, ai/fondamentali/deep-learning, ai/mlops/infrastruttura-gpu, ai/modelli/modelli-open-source]
official_docs: https://huggingface.co/docs/trl/index
status: needs-review
difficulty: expert
last_updated: 2026-10-03
last_verified: 2026-10-03
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
- Richiede pesi BF16 + gradienti + optimizer states Adam (FP32 master weights, momento, varianza)
  → ~16 byte/parametro in mixed precision
- Llama 3.1 8B full FT: ~128 GB VRAM (8B × 16 byte), prima delle attivazioni
- Raramente necessario: quasi sempre PEFT è sufficiente
```

**Quando usare:** solo con dataset molto grandi (continued pre-training, cambio di lingua/dominio profondo) e accesso a cluster GPU. Per adattare stile, formato o competenze di task, PEFT basta e costa 10-100× meno.

!!! note "Modelli negli esempi"
    Gli esempi usano Llama 3.1 8B/70B per continuità con i numeri di VRAM. Il flusso è identico per le famiglie open-weight più recenti (Llama 4, Qwen3, Gemma 3, Mistral…): cambiano `model_id`, i nomi dei `target_modules` (verificali con `print(model)`) e il chat template.

!!! warning "API TRL/Transformers in evoluzione"
    `trl` cambia API spesso. Gli esempi seguono le versioni recenti: `processing_class` al posto di `tokenizer`, `eval_strategy` al posto di `evaluation_strategy`. Se vedi `TypeError: unexpected keyword argument`, controlla la versione installata (`pip show trl transformers`) e il changelog.
    <!-- REVIEW: verificare nomi parametri SFTConfig (max_length vs max_seq_length), DPOConfig (max_prompt_length) sulla versione TRL corrente -->

??? info "Quando NON fare fine-tuning"
    Se serve conoscenza aggiornata o proprietaria, di solito è meglio il RAG: il fine-tuning insegna stile e comportamento, non è un buon canale per iniettare fatti che cambiano. Parti sempre da prompt engineering e RAG; fine-tuna quando hai un task ripetitivo con metrica misurabile.

## 2. LoRA — Low-Rank Adaptation

LoRA congela i pesi originali del modello e inserisce matrici di aggiornamento a basso rango (rank) nei layer Transformer. Solo queste matrici piccole vengono addestrate.

### Come Funziona

```
Peso originale W (frozen): d × k  (es. 4096 × 4096 = 16.7M parametri)

LoRA aggiunge:
  B: d × r  (es. 4096 × 16 = 65.5K parametri, inizializzata a zero)
  A: r × k  (es. 16 × 4096 = 65.5K parametri, init gaussiana)

Output = W·x + (B·A)·x × (alpha/r)

Parametri addestrati: r × (d + k) = 131K invece di 16.7M
Riduzione: 99.2% dei parametri!
```

**Perché funziona:** l'ipotesi del paper è che l'aggiornamento `ΔW` necessario per adattare il modello abbia rango intrinseco basso, quindi lo si approssima con `B·A`. `B` parte da zero, quindi a inizio training il modello è identico al base. A fine training `B·A` si può sommare a `W` (merge, vedi sezione 8) senza costo extra in inferenza.

| Hyperparametro | Descrizione | Valori Tipici |
|---------------|-------------|---------------|
| `r` (rank) | Dimensione delle matrici LoRA | 4, 8, 16, 32, 64 |
| `alpha` | Scaling factor (alpha/r) | Uguale a r o doppio (es. r=16, alpha=32) |
| `target_modules` | Layer su cui applicare LoRA | q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj, down_proj |
| `dropout` | Dropout nelle matrici LoRA | 0.05-0.1 |

```python
import torch
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
# trainable params: 41,943,040 || all params: 8,072,204,288 || trainable%: 0.5196
# (r=16 su tutti e 7 i moduli lineari di Llama 3.1 8B)
```

## 3. QLoRA — LoRA con Quantizzazione 4-bit

QLoRA combina LoRA con la quantizzazione 4-bit del modello base (NF4 = NormalFloat 4-bit). Permette di fare fine-tuning di modelli enormi su GPU consumer.

```
QLoRA = modello base in NF4 (4-bit) + adapter LoRA in BF16

Llama 3.1 8B:
  FP16:   ~16 GB VRAM
  NF4:    ~4.5 GB VRAM → si fa fine-tuning su GPU da 8-12 GB!

Llama 3.1 70B:
  FP16:  ~140 GB solo pesi (2× 80 GB minimo, più training: 4× 80 GB)
  NF4:   ~40 GB solo pesi (1× A100/H100 80 GB, o 2× RTX 4090 con batch piccoli)
```

**Perché NF4:** i pesi di un LLM sono distribuiti circa normalmente; NF4 posiziona i 16 livelli di quantizzazione sui quantili di una normale, perdendo meno informazione di un INT4 uniforme. Il *double quant* quantizza anche le costanti di scala (~0,4 bit/parametro risparmiati). I gradienti passano attraverso i pesi quantizzati (dequantizzati al volo in BF16) e aggiornano solo gli adapter LoRA.

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

Unsloth è una libreria che ottimizza il fine-tuning con kernel custom Triton/CUDA: dichiara 2-5× di velocità rispetto a HuggingFace vanilla e 50-70% in meno di VRAM (numeri del vendor, variano con modello e hardware). Si integra con TRL (`SFTTrainer`, `DPOTrainer`, `GRPOTrainer`).

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
        "input": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: myapp\nspec:\n  template:\n    spec:\n      containers:\n      - name: app\n        image: myapp:latest\n        securityContext:\n          runAsUser: 0",
        "output": "PROBLEMI IDENTIFICATI:\n1. **CRITICO** - runAsUser: 0: Il container gira come root. Usa runAsNonRoot: true e specifica runAsUser con UID non-root (es. 1000).\n2. **HIGH** - Nessun SecurityContext a livello pod.\n3. **MEDIUM** - Tag 'latest' per l'immagine: usa tag specifici per reproducibilità."
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

Il formato conta meno del contenuto, ma deve essere coerente: usa sempre il chat template del modello (`tokenizer.apply_chat_template`) sia in training sia in inferenza, altrimenti il modello vede token di controllo diversi da quelli appresi.

```python
import json

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

        # Filtra rifiuti/boilerplate tipici di dati sintetici generati da altri LLM
        # (euristica grezza: non rileva vere allucinazioni, per quelle serve verifica
        # umana o LLM-as-judge)
        boilerplate_patterns = [
            "come ia non", "come modello ai", "as an ai", "non posso aiutarti"
        ]
        if any(p in response.lower() for p in boilerplate_patterns):
            continue

        filtered.append(ex)

    # Dedup esatta (per near-duplicates usa MinHash/embedding)
    return list({json.dumps(ex, sort_keys=True): ex for ex in filtered}.values())
```

## 5. Supervised Fine-Tuning (SFT)

Il SFT addestra il modello su coppie (instruction, response) di alta qualità.

```python
import json
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# Prepara dataset in formato conversazionale ("messages"):
# SFTTrainer applica da solo il chat template del tokenizer (niente token a mano)
def format_alpaca(example: dict) -> dict:
    """Converte un esempio Alpaca in messaggi chat."""
    user = example["instruction"]
    if example.get("input"):
        user += "\n\n" + example["input"]
    return {"messages": [
        {"role": "system", "content": "Sei un esperto DevOps e SRE."},
        {"role": "user", "content": user},
        {"role": "assistant", "content": example["output"]},
    ]}

# Carica e formatta dataset
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
    eval_strategy="steps",
    eval_steps=100,
    save_strategy="steps",
    save_steps=200,                  # multiplo di eval_steps (richiesto da load_best_model_at_end)
    save_total_limit=3,
    load_best_model_at_end=True,
    max_length=4096,                 # nelle versioni TRL meno recenti: max_seq_length
    assistant_only_loss=False,       # True = loss solo sui token dell'assistant (richiede template con generation tags)
    report_to="wandb",               # traccia su W&B
)

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    args=training_args,
    train_dataset=train_val["train"],
    eval_dataset=train_val["test"],
)

# Training!
trainer.train()
trainer.save_model()
```

## 6. RLHF — Reinforcement Learning from Human Feedback

RLHF è la tecnica usata per allineare i modelli alle preferenze umane (resa popolare da InstructGPT/ChatGPT). Il flusso: SFT → reward model addestrato su preferenze umane → ottimizzazione della policy con RL (PPO) contro il reward model, con penalità KL per non allontanarsi dal modello SFT. È complessa da implementare correttamente: 3-4 modelli in memoria e forte sensibilità agli iperparametri.

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
    model=reward_model,     # copia del SFT model con head lineare (AutoModelForSequenceClassification, num_labels=1)
    processing_class=tokenizer,
    args=reward_config,
    train_dataset=preference_dataset,
)
reward_trainer.train()
```

### Step 3: PPO Training

!!! warning "API legacy"
    Lo snippet sotto usa l'interfaccia classica di `PPOTrainer` (`step`, `generate`, `log_stats`), rimossa/riscritta nelle versioni recenti di TRL (la nuova API è basata su `PPOConfig` + `reward_model`/`value_model` e `trainer.train()`). Serve a illustrare il ciclo concettuale (generate → reward → update con KL penalty); per codice eseguibile segui la documentazione TRL della tua versione. Nella pratica, per la maggior parte dei casi, vedi DPO e GRPO più sotto.

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
        "chosen": """FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
USER node
EXPOSE 3000
CMD ["node", "server.js"]

Note di sicurezza:
- Alpine riduce attack surface
- npm ci invece di npm install per reproducibilità
- USER node: non gira come root
- Tag specifico (non latest) per build riproducibili""",
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
    learning_rate=5e-7,    # DPO usa LR molto più basso di SFT (full FT); con LoRA ~5e-6
    beta=0.1,              # temperatura KL — più alto = più conservativo
    bf16=True,
    max_prompt_length=1024,
    max_length=2048,
)

dpo_trainer = DPOTrainer(
    model=model,           # SFT model da allineare
    ref_model=ref_model,   # copia frozen del SFT model (None se model ha adapter PEFT:
                           # il reference è il modello con adapter disattivato → risparmia VRAM)
    args=dpo_config,
    train_dataset=Dataset.from_list(dpo_dataset),
    processing_class=tokenizer,
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

### GRPO e RLVR — RL per reasoning

Dal 2025 il metodo RL dominante per modelli di ragionamento (stile DeepSeek-R1) è **GRPO** (Group Relative Policy Optimization) con **RLVR** (Reinforcement Learning with Verifiable Rewards). Invece di un reward model appreso, il reward è una funzione deterministica (test che passano, risposta matematica esatta, output che rispetta uno schema). Per ogni prompt si campiona un gruppo di risposte e il vantaggio di ciascuna è calcolato rispetto alla media del gruppo: niente value model, meno memoria di PPO.

**Quando usarlo:** task con verifica automatica (codice, matematica, parsing strutturato, generazione di manifest validabili con `kubectl --dry-run`/`kubeconform`). Per preferenze soggettive (tono, stile) resta DPO.

```python
from trl import GRPOTrainer, GRPOConfig

def reward_valid_json(completions, **kwargs) -> list[float]:
    """Reward verificabile: 1.0 se l'output è JSON valido, altrimenti 0.0."""
    rewards = []
    for c in completions:
        text = c if isinstance(c, str) else c[0]["content"]  # formato standard vs conversazionale
        try:
            json.loads(text)
            rewards.append(1.0)
        except ValueError:
            rewards.append(0.0)
    return rewards

trainer = GRPOTrainer(
    model="./llama3-devops-ft",          # modello SFT di partenza
    reward_funcs=reward_valid_json,
    args=GRPOConfig(output_dir="./grpo_model", num_generations=8, bf16=True),
    train_dataset=prompts_dataset,       # colonna "prompt"
)
trainer.train()
```

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

In alternativa al merge: vLLM può servire l'adapter a runtime (`--enable-lora --lora-modules nome=./adapter`), utile per molti adapter su un solo base model.

```bash
# Quantizza per deployment (richiede llama.cpp clonato e compilato)
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
| Llama 3.1 70B | QLoRA (NF4) | 48 GB | 80 GB | 1× A100/H100 80GB |
| Llama 3.1 70B | LoRA (BF16) | 160 GB | 4×80 GB | 4× A100 80GB |
| Llama 3.1 405B | QLoRA (NF4) | ~250 GB | 4×80 GB | 4× H100 80GB (o 8×) |

*Stime indicative: dipendono da `max_seq_length`, batch size e gradient checkpointing.*

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
