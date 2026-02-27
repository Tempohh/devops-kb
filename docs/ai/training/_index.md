---
title: "Training e Fine-Tuning LLM"
slug: training-llm
category: ai
tags: [training, fine-tuning, rlhf, lora, dataset]
search_keywords: [fine-tuning LLM, training LLM, LoRA, QLoRA, RLHF, DPO, PEFT, quando fare fine-tuning, dataset training, SFT supervised fine-tuning, addestramento modello, personalizzare LLM, istruzione fine-tuning, preference optimization]
parent: ai/_index
related: [ai/fondamentali/deep-learning, ai/training/fine-tuning, ai/training/valutazione, ai/mlops/infrastruttura-gpu, ai/mlops/model-serving]
official_docs: https://huggingface.co/docs/trl/index
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Training e Fine-Tuning LLM

## Panoramica

Il fine-tuning è il processo di adattamento di un LLM pre-addestrato a un task o dominio specifico, aggiornando i suoi pesi su un dataset curato. È la terza opzione nel toolkit di personalizzazione degli LLM, dopo il prompt engineering e il RAG. Capire quando fare fine-tuning — e quando non farlo — è critico: il fine-tuning richiede dati di qualità, compute GPU, expertise ML, e porta con sé rischi di degradazione se fatto male.

La regola di base: il fine-tuning serve per cambiare **come** il modello risponde (stile, formato, tono, persona), non **cosa sa**. Se hai bisogno che il modello conosca dati aggiornati o privati, usa RAG. Se hai bisogno che il modello segua istruzioni specifiche, prova prima con il prompt engineering (è gratuito e reversibile).

## Decision Tree: Fine-Tuning vs Prompt Engineering vs RAG

```
HAI UN PROBLEMA CON L'OUTPUT DEL MODELLO?
│
├── Il modello non conosce le informazioni necessarie?
│   → RAG (Retrieval-Augmented Generation)
│   Non fare fine-tuning per "insegnare fatti" — il fine-tuning è inefficiente
│   come meccanismo di memorizzazione rispetto a RAG
│
├── Il modello risponde nella forma sbagliata (stile, formato, lunghezza)?
│   ├── Puoi risolvere con istruzioni nel system prompt?
│   │   → Prompt Engineering (prova prima — è gratis e reversibile)
│   └── Il prompt engineering non basta per il volume/qualità richiesta?
│       → Fine-Tuning su poche centinaia di esempi
│
├── Il modello deve seguire pattern molto specifici del dominio?
│   (es. formato output proprietario, terminologia interna, stile aziendale)
│   → Fine-Tuning con dataset di esempi di alta qualità
│
├── Il modello deve gestire un task molto specifico ad alta frequenza?
│   (es. classificazione log proprietari, estrazione entità da doc interni)
│   → Fine-Tuning (can be trained on synthetic data)
│
├── Hai bisogno di un modello più veloce/piccolo per lo stesso task?
│   → Distillation o Fine-Tuning su modello piccolo con output del modello grande
│
└── Vuoi migliorare la safety o l'alignment?
    → RLHF o DPO (richiede expertise avanzata)
```

## Quando NON Fare Fine-Tuning

- **Non hai almeno 100-500 esempi di alta qualità**: il fine-tuning su pochi dati mediocri peggiora il modello
- **Il problema si risolve con il prompt**: testa sempre prima con prompt engineering sistematico
- **Hai dati che cambiano frequentemente**: il fine-tuning è statico, il RAG è aggiornabile
- **Non hai GPU o expertise ML**: il costo operativo supera il beneficio
- **Stai usando API closed (Claude, GPT-4)**: Anthropic non espone API di fine-tuning pubbliche per Claude — usa system prompt e few-shot

!!! note "Claude e Fine-Tuning"
    Anthropic non offre API di fine-tuning pubblica per Claude (a differenza di OpenAI che offre fine-tuning per GPT-3.5 e alcuni modelli GPT-4). Per personalizzare Claude, usa system prompt dettagliato, XML tags, few-shot examples, e prompt caching. Per task dove il fine-tuning è indispensabile, considera modelli open weight (Llama, Mistral).

## Risorse Necessarie

| Scenario | Modello | Metodo | GPU Minima | Tempo |
|----------|---------|--------|-----------|-------|
| Classificazione task | Llama 3.1 8B | QLoRA | 1× RTX 4090 (24GB) | 1-4 ore |
| Instruction following | Llama 3.1 8B | QLoRA | 1× RTX 4090 (24GB) | 4-12 ore |
| Domain adaptation | Llama 3.1 70B | QLoRA | 2× A100 40GB | 12-48 ore |
| Full fine-tuning | Llama 3.1 8B | Full | 4× A100 80GB | 1-3 giorni |
| RLHF pipeline | Qualsiasi | PPO+RM | Multi-GPU | Settimane |

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Fine-Tuning — LoRA, QLoRA, RLHF, DPO**

    ---

    PEFT e parameter-efficient methods. Dataset preparation. QLoRA su hardware consumer. RLHF pipeline completa. DPO come alternativa.

    [:octicons-arrow-right-24: Fine-Tuning](fine-tuning.md)

-   **Valutazione LLM — Benchmark e Evals**

    ---

    Benchmark standard (MMLU, HumanEval, MATH). Evals custom. LLM-as-Judge. RAGAS per RAG. Framework di valutazione.

    [:octicons-arrow-right-24: Valutazione](valutazione.md)

</div>

## Riferimenti

- [HuggingFace TRL — Training LLM](https://huggingface.co/docs/trl/) — Libreria per SFT, PPO, DPO
- [Unsloth](https://github.com/unslothai/unsloth) — Fine-tuning ottimizzato (2-5× più veloce, meno VRAM)
- [LoRA Paper (Hu et al., 2021)](https://arxiv.org/abs/2106.09685) — Paper originale LoRA
- [QLoRA (Dettmers et al., 2023)](https://arxiv.org/abs/2305.14314) — Fine-tuning con quantizzazione
- [DPO (Rafailov et al., 2023)](https://arxiv.org/abs/2305.18290) — Direct Preference Optimization
