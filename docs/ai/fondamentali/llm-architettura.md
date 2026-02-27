---
title: "Architettura LLM — Transformer, Attention e Pre-training"
slug: llm-architettura
category: ai
tags: [llm, transformer, attention, tokenization, pre-training, gpt, bert, autoregressive]
search_keywords: [transformer architecture, attention mechanism, self-attention, multi-head attention, positional encoding, llm architecture, autoregressive model, causal language model, pre-training, next token prediction, BERT, GPT, decoder-only, encoder-decoder, feed forward network, layer normalization, residual connection, KV cache, flash attention, rotary positional embedding, RoPE, grouped query attention, GQA, mixture of experts, MoE]
parent: ai/fondamentali/_index
related: [ai/tokens-context/tokenizzazione, ai/tokens-context/context-window, ai/modelli/claude, ai/training/fine-tuning]
official_docs: https://arxiv.org/abs/1706.03762
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Architettura LLM — Transformer, Attention e Pre-training

## Panoramica

I **Large Language Models** sono reti neurali con miliardi di parametri, addestrate su enormi corpora di testo, capaci di generare, comprendere, ragionare e seguire istruzioni in linguaggio naturale. La loro architettura comune è il **Transformer**, introdotto nel 2017 con il paper "Attention Is All You Need" (Vaswani et al., Google Brain). Prima dei Transformer, i modelli per sequenze erano RNN/LSTM — lenti, con difficoltà sui contesti lunghi, e non parallelizzabili. Il Transformer ha risolto tutti e tre i problemi attraverso un meccanismo chiamato **attention**.

Capire l'architettura dei LLM è fondamentale per: scegliere il modello corretto, ottimizzare i prompt, comprendere i limiti (context window, token cost), e prendere decisioni architetturali su fine-tuning vs RAG vs prompt engineering.

## Il Problema: Modellare il Linguaggio

Un language model risponde a una domanda fondamentale:

> **Data una sequenza di token, qual è il token più probabile successivo?**

Formalmente: dato il contesto `[t₁, t₂, ..., tₙ]`, il modello impara la distribuzione di probabilità `P(tₙ₊₁ | t₁, ..., tₙ)`.

Un **autoregressive language model** (GPT-style, decoder-only) genera token uno alla volta, usando ogni token generato come input per il successivo. Questo è il meccanismo dietro ChatGPT, Claude, Llama, ecc.

```
Input:  "La capitale d'Italia è"
Step 1: P("Roma"=0.92, "Milano"=0.03, "Parigi"=0.01, ...) → genera "Roma"
Step 2: P("."=0.85, ","=0.08, "e"=0.04, ...) → genera "."
```

## Architettura Transformer — Panoramica

```
INPUT TEXT
    │
    ▼
┌─────────────────┐
│  Tokenizer      │  "Ciao mondo" → [1234, 5678]
└────────┬────────┘
         │
    ▼
┌─────────────────┐
│  Embedding      │  token_id → vettore denso ℝᵈ
│  Layer          │  es. d_model = 4096
└────────┬────────┘
         │
    ▼
┌─────────────────┐
│  Positional     │  aggiunge informazione sulla posizione
│  Encoding       │  (RoPE nei modelli moderni)
└────────┬────────┘
         │
    ▼
┌─────────────────────────────────────┐
│  Transformer Block × N layers       │  es. N=32 (7B), N=80 (70B)
│                                     │
│  ┌───────────────────────────────┐  │
│  │  LayerNorm (pre-norm)         │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Multi-Head Attention         │  │
│  │  (Causal Self-Attention)      │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Residual Connection (+)      │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  LayerNorm (pre-norm)         │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Feed-Forward Network (FFN)   │  │
│  │  (SwiGLU / GELU activation)  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Residual Connection (+)      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         │
    ▼
┌─────────────────┐
│  Final LayerNorm│
└────────┬────────┘
         │
    ▼
┌─────────────────┐
│  LM Head        │  proietta su vocab size (es. 128K)
│  (Linear + Softmax) → distribuzione di probabilità
└─────────────────┘
```

## Self-Attention — Il Cuore del Transformer

L'**attention** è il meccanismo che permette a ogni token di "guardare" e pesare la rilevanza di tutti gli altri token nel contesto. È questo che supera il limite degli RNN di dipendere da stati compressi.

### Query, Key, Value

Per ogni token, il layer di attention produce 3 vettori:
- **Query (Q)**: "cosa sto cercando?"
- **Key (K)**: "cosa ho da offrire?"
- **Value (V)**: "qual è il mio contenuto informativo?"

```python
# Dimensioni: (batch, seq_len, d_model)
# Proiezioni lineari apprese durante il training
Q = X @ W_Q  # (batch, seq_len, d_k)
K = X @ W_K  # (batch, seq_len, d_k)
V = X @ W_V  # (batch, seq_len, d_v)

# Attention scores: dot product tra Query e Key
scores = Q @ K.transpose(-2, -1)  # (batch, seq_len, seq_len)
scores = scores / math.sqrt(d_k)  # scaling per stabilità numerica

# Causal mask: un token può "vedere" solo i token PRECEDENTI
# (autoregressive: nessun look-ahead)
mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()
scores = scores.masked_fill(mask, float('-inf'))

# Softmax: converte scores in pesi 0-1 che sommano a 1
attn_weights = torch.softmax(scores, dim=-1)  # (batch, seq_len, seq_len)

# Output: somma pesata dei Value
output = attn_weights @ V  # (batch, seq_len, d_v)
```

### Multi-Head Attention

Invece di un singolo meccanismo di attention, si usano **h head paralleli** (es. h=32), ognuno con le proprie proiezioni W_Q, W_K, W_V. Ogni head può specializzarsi su diversi tipi di relazioni:
- Head 1: relazioni sintattiche soggetto-verbo
- Head 2: coreferenza pronominale
- Head 3: dipendenze a lunga distanza
- Head N: pattern semantici...

```python
# Ogni head lavora su d_k = d_model / h dimensioni
# L'output di tutti gli head viene concatenato e riproiettato
multi_head_output = concat([head_1, head_2, ..., head_h]) @ W_O
```

### Feed-Forward Network (FFN)

Ogni Transformer block ha, dopo l'attention, una FFN a 2 layer. In Llama/Claude usa **SwiGLU**:

```python
# SwiGLU (più efficiente di GELU standard)
def ffn_swiglu(x, W1, W2, W3):
    gate = F.silu(x @ W1)   # gate con Swish activation
    proj = x @ W3            # proiezione parallela
    return (gate * proj) @ W2

# d_ffn è tipicamente 4× d_model (es. 4096 → 16384 o 11008 per SwiGLU)
```

## Positional Encoding — RoPE

I Transformer non hanno intrinsecamente nozione di ordine (l'attention è invariante alla posizione). Il positional encoding aggiunge questa informazione.

I modelli moderni usano **Rotary Positional Embedding (RoPE)**, introdotto in RoFormer e adottato da Llama, Mistral, Claude:

```python
# RoPE: applica rotazione ai vettori Q e K basata sulla posizione
# Proprietà chiave: il dot product Q_m · K_n dipende solo dalla distanza (m-n)
# Questo favorisce la generalizzazione a lunghezze non viste in training

def apply_rotary_emb(q, k, freqs_cos, freqs_sin):
    q_r, q_i = q[..., ::2], q[..., 1::2]   # parti reale e immaginaria
    k_r, k_i = k[..., ::2], k[..., 1::2]

    # Rotazione 2D nello spazio complesso
    q_out_r = q_r * freqs_cos - q_i * freqs_sin
    q_out_i = q_r * freqs_sin + q_i * freqs_cos
    k_out_r = k_r * freqs_cos - k_i * freqs_sin
    k_out_i = k_r * freqs_sin + k_i * freqs_cos

    return interleave(q_out_r, q_out_i), interleave(k_out_r, k_out_i)
```

**Vantaggio di RoPE**: L'estensione del context window (es. da 4K a 128K) può essere ottenuta con **YaRN** (Yet another RoPE extensioN) modificando le frequenze senza re-training completo.

## Grouped Query Attention (GQA)

Il KV cache durante l'inference occupa molta memoria. **GQA** (usato in Llama 3, Mistral, Claude) riduce questo costo condividendo le K e V tra gruppi di Q head:

```
Standard MHA:   32 Q heads, 32 K heads, 32 V heads  → costo KV pieno
GQA (g=8):      32 Q heads,  4 K heads,  4 V heads  → KV ridotto 8×
MQA:            32 Q heads,  1 K head,   1 V head   → KV minimo (peggiore qualità)
```

## Dimensionamento Modelli

| Modello | Parametri | Layers (N) | d_model | Heads | d_head | Context |
|---------|-----------|-----------|---------|-------|--------|---------|
| Llama 3.2 1B | 1B | 16 | 2048 | 32 | 64 | 128K |
| Llama 3.1 8B | 8B | 32 | 4096 | 32 | 128 | 128K |
| Llama 3.1 70B | 70B | 80 | 8192 | 64 | 128 | 128K |
| Mistral 7B | 7B | 32 | 4096 | 32 | 128 | 32K |
| Claude 3 Haiku | ~20B est. | — | — | — | — | 200K |
| GPT-4 | ~1.8T est. (MoE) | — | — | — | — | 128K |

## Pre-training

### Dati e Scale

Il pre-training è la fase costosa che genera un **foundation model**. Richiede:

```
Dati:     1-15 Trillion token
          (Common Crawl, GitHub, Wikipedia, libri, arxiv, code...)
Compute:  GPT-4 ≈ 25.000 A100 GPU × 90-100 giorni
          Llama 3.1 70B ≈ 6.4M GPU-ore su H100
Hardware: Cluster GPU interconnessi con InfiniBand (400Gb/s)
```

### Obiettivo di Training

Per modelli **decoder-only** (GPT-style): **Next Token Prediction** via cross-entropy loss:

```python
# Per ogni posizione, il modello predice il prossimo token
# Loss = -Σ log P(tᵢ | t₁, ..., tᵢ₋₁)

logits = model(input_ids)         # (batch, seq_len, vocab_size)
loss = F.cross_entropy(
    logits[:, :-1].reshape(-1, vocab_size),   # predizioni
    input_ids[:, 1:].reshape(-1)              # target: il token successivo reale
)
```

**Emerge capability**: durante il pre-training su next-token prediction, il modello sviluppa spontaneamente capacità non esplicitamente addestrate: ragionamento, matematica, coding, multilingual — fenomeno chiamato **emergent abilities**, che appaiono improvvisamente superata una soglia di parametri.

### Scaling Laws

La ricerca di Kaplan et al. (OpenAI, 2020) e Hoffmann et al. (DeepMind "Chinchilla", 2022) ha stabilito le **leggi di scala** per i LLM:

```
Optimal token count = 20 × model_parameters

Es. modello 7B → training ottimale su 140B token (Chinchilla-optimal)
    (Llama 3.1 70B è trainato su 15T token → over-trained per inference efficiente)
```

**Trade-off over-training**: un modello più piccolo trainato su più dati è spesso preferibile a un modello grande trainato con meno dati, perché:
- Inference più veloce e economica
- Può essere deployato su hardware consumer
- Performance comparabili per molti task

## Dalla Pretraining alla Chat — RLHF e Instruction Tuning

Un foundation model pre-trained sa completare testo ma non sa seguire istruzioni. La pipeline per creare un assistente AI è:

```
1. PRE-TRAINING
   Foundation model (next token prediction su web-scale text)

2. SUPERVISED FINE-TUNING (SFT)
   Esempi curati di (instruction → response) di alta qualità
   Insegna al modello il formato instruction-following

3. REWARD MODEL TRAINING
   Human raters confrontano coppie di risposte (quale è migliore?)
   Addestra un reward model che predice la preferenza umana

4. RLHF / PPO
   Ottimizza il modello SFT con RL usando il reward model come segnale
   Tecnicamente: PPO (Proximal Policy Optimization) o REINFORCE

5. (Opzionale) DPO / RLAIF
   Direct Preference Optimization (più stabile di PPO)
   RLAIF: usa un altro LLM invece di umani per le preferenze
```

### Constitutional AI (Anthropic)

Anthropic usa una variante chiamata **Constitutional AI (CAI)**:

```
1. SFT normale

2. CRITIQUE & REVISION (AI-supervised)
   Il modello genera una risposta a un prompt dannoso
   Lo stesso modello critica la risposta in base a una "costituzione"
   (lista di principi: "non aiutare con azioni illegali", "sii onesto", ...)
   Il modello revisiona la risposta fino a soddisfare i principi

3. RLHF con AI feedback (RLAIF)
   Il reward model è addestrato su preferenze generate da AI
   (invece che esclusivamente da umani)
   Riduce la dipendenza da labeling umano ad alto costo

Vantaggio: più scalabile, più consistente, meno soggetto a bias degli annotatori
```

## Flash Attention

L'attention standard ha complessità **O(n²)** in memoria (la matrice di attention scores è n×n). Per context window di 100K token, questo è proibitivo.

**FlashAttention** (Dao et al., 2022) risolve il problema con:
- **Tiling**: divide il calcolo in blocchi che stanno nella SRAM (cache GPU), evitando round-trip con HBM (memoria GPU principale)
- **Recomputation**: in backward pass, ricalcola l'attention invece di tenerla in memoria
- Stessa matematica, 3-5× più veloce, stessa output

```
Standard Attention: legge/scrive HBM O(n²) volte
FlashAttention:     legge/scrive HBM O(n) volte (tiling su SRAM)

Per n=100K: ~10.000× meno read/write HBM
```

## Mixture of Experts (MoE)

GPT-4 e modelli come Mixtral usano **MoE**: invece di un singolo FFN per ogni layer, ci sono **N expert FFN** e un router che attiva solo k di essi per ogni token.

```python
# MoE Layer
def moe_forward(x, experts, router):
    # Router: decide quale expert usare
    router_logits = router(x)  # (batch, seq, n_experts)
    expert_weights, expert_indices = torch.topk(
        torch.softmax(router_logits, dim=-1),
        k=2  # top-2 experts attivi per token
    )

    # Esegui solo i 2 expert selezionati
    output = sum(expert_weights[i] * experts[expert_indices[i]](x)
                 for i in range(2))
    return output

# Mixtral 8×7B: 8 expert da 7B ciascuno
# Ma solo 2 attivi per token → compute come 13B, capacità come 47B
```

**Vantaggio**: aumenta la capacità del modello (più parametri totali) senza aumentare il compute per token.

## Confronto Architetture

| Aspetto | Encoder-Only (BERT) | Encoder-Decoder (T5) | Decoder-Only (GPT/Claude) |
|---------|--------------------|--------------------|--------------------------|
| Uso tipico | Classification, NER, embedding | Seq2Seq, traduzione | Generazione, chat, coding |
| Attention | Bidirezionale | Cross-attention | Causal (unidirezionale) |
| Pre-training | MLM (masked tokens) | Span corruption | Next token prediction |
| VRAM inference | Bassa | Media | Alta (KV cache) |
| Esempi | BERT, RoBERTa, DeBERTa | T5, BART, mT5 | GPT, Claude, Llama, Mistral |
| Trend 2024-26 | Nicchia (embedding) | In declino | Dominante |

## Scaling e Limiti

### Il Problema dell'Hallucination

I LLM generano token basandosi su pattern statistici, non su conoscenza verificata. L'**hallucination** è la generazione di contenuto plausibile ma fattualmente errato. Cause:
- Il modello ha visto dati conflittuali in training
- Domanda fuori distribuzione (knowledge cutoff)
- Il modello "compila" una risposta statistically likely anche senza basi fattuali

**Mitigazione**: RAG (fornire contesto aggiornato), temperature 0 per task fattuali, chain-of-thought per reasoning, system prompt con istruzioni esplicite di ammettere incertezza.

### Knowledge Cutoff

Il modello non sa nulla di eventi successivi alla data di cutoff del training. Claude 4.6 ha cutoff **agosto 2025**.

## Riferimenti

- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — Paper originale Transformer
- [Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165) — GPT-3
- [Training language models to follow instructions](https://arxiv.org/abs/2203.02155) — InstructGPT/RLHF
- [Constitutional AI](https://arxiv.org/abs/2212.08073) — Anthropic
- [FlashAttention-2](https://arxiv.org/abs/2307.08691)
- [Llama 3 Technical Report](https://arxiv.org/abs/2407.21783)
- [Chinchilla Scaling Laws](https://arxiv.org/abs/2203.15556)
