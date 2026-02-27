---
title: "Tokens & Context Window"
slug: tokens-context
category: ai
tags: [tokens, tokenization, context-window, kv-cache]
search_keywords: [token LLM, tokenizzazione, context window, finestra di contesto, KV cache, prompt length, costo token, tiktoken, subword, BPE, byte pair encoding, input length, output length, max tokens]
parent: ai/_index
related: [ai/fondamentali/_index, ai/sviluppo/prompt-engineering, ai/sviluppo/rag, ai/mlops/infrastruttura-gpu]
official_docs: https://platform.openai.com/tokenizer
status: complete
difficulty: beginner
last_updated: 2026-02-27
---

# Tokens & Context Window

## Panoramica

I token sono l'unità fondamentale che gli LLM usano per leggere e scrivere testo. Capire cosa sono i token, come si contano e come impattano sul costo e sul comportamento del modello è essenziale per chiunque lavori con LLM in produzione. Non capire i token porta a sorprese sul costo, a prompt che vengono troncati silenziosamente, e a inferenze errate su cosa il modello "vede" effettivamente.

Un token non è una parola: può essere una parola intera, parte di una parola, un carattere speciale, o una sequenza di spazi. "tokenizzazione" in italiano può diventare 4-5 token. Un URL è molti token. Il codice sorgente è spesso più token del testo equivalente. Queste differenze hanno implicazioni dirette sul costo e sulla progettazione dei prompt.

La context window è la "memoria di lavoro" del modello: l'insieme di token che il modello vede durante una singola inferenza. Tutto ciò che è fuori dalla context window è invisibile al modello, come se non esistesse. Progettare applicazioni LLM significa progettare come riempire questa finestra in modo efficace.

## Concetti Fondamentali

### Token ≠ Parola

Regola empirica per stime rapide:
- **Inglese**: 1 token ≈ 0.75 parole, 100 token ≈ 75 parole
- **Italiano**: 1 token ≈ 0.6-0.7 parole (leggermente meno efficiente dell'inglese)
- **Codice**: più denso, 1 token ≈ 3-5 caratteri
- **CJK** (cinese, giapponese, coreano): 1 carattere ≈ 1-3 token
- **Numeri grandi**: ogni cifra può diventare un token separato

Esempi concreti:

```
"Hello"          → [Hello]          = 1 token
"tokenization"   → [token][ization] = 2 token
"tokenizzazione" → [token][iz][zaz][ione] = 4 token (circa)
"API_KEY_2024"   → [API][_][KEY][_][2024] = 5 token
"https://example.com/api/v1/users" → ~10-15 token
"1234567890"     → [1][2][3][4][5][6][7][8][9][0] = fino a 10 token
```

### Context Window

La context window definisce il numero massimo di token che il modello processa in una singola inferenza. Include sia l'input (prompt + sistema + storia conversazione) che l'output (risposta generata).

```
Context Window = Input tokens + Output tokens
               = system_prompt + conversation_history + user_message + response

Esempio con Claude 3.5 Sonnet (200K context):
├── System prompt:          500 token
├── Conversation history:   5000 token
├── User message:           2000 token
└── Response (max):         8192 token (configurabile)
    Total:                  ~16K token su 200K disponibili
```

| Modello | Context Window | Nota |
|---------|---------------|------|
| Claude 3.5 Sonnet/Haiku | 200K | 200.000 token input |
| Claude 3 Opus | 200K | |
| GPT-4o | 128K | |
| Gemini 1.5 Pro | 1M | 1 milione di token |
| Gemini 2.0 Flash | 1M | |
| Llama 3.1 | 128K | |
| Mistral 7B | 32K | (sliding window) |
| Gemma 2 | 8K | Limitato |

### KV Cache

Durante l'inferenza, il Transformer calcola matrici Key e Value per ogni token nel contesto. Invece di ricalcolarle ad ogni step di generazione, vengono salvate in memoria (KV Cache). Questo riduce drasticamente la latenza di generazione ma richiede VRAM significativa.

```
KV Cache size = 2 × num_layers × num_kv_heads × head_dim × seq_len × dtype_bytes

Esempio Llama 3.1 8B (FP16):
= 2 × 32 × 8 × 128 × 128.000 × 2
= ~16 GB solo per KV cache con context piena di 128K
```

Questo spiega perché context window grandi richiedono molta VRAM e perché il costo dell'inferenza cresce con la lunghezza del contesto.

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Tokenizzazione**

    ---

    BPE (Byte Pair Encoding), vocab size, tiktoken, conteggio token, differenze tra lingue e modelli. Calcolo costo.

    [:octicons-arrow-right-24: Tokenizzazione](tokenizzazione.md)

-   **Context Window e KV Cache**

    ---

    Come funziona la context window, KV cache in dettaglio, strategie per contesti lunghi, primacy/recency bias.

    [:octicons-arrow-right-24: Context Window](context-window.md)

</div>

## Regole Pratiche Rapide

!!! tip "Stima veloce dei token"
    - 1 pagina A4 di testo ≈ 500-700 token
    - 1 file Python da 100 righe ≈ 800-1500 token
    - 1 file YAML Kubernetes ≈ 300-600 token
    - 1 log di 1000 righe ≈ 3000-8000 token

!!! warning "Troncamento silenzioso"
    Se l'input supera la context window, i token vengono troncati silenziosamente (solitamente dall'inizio o dalla fine, dipende dall'implementazione). Il modello non genera un errore — produce semplicemente una risposta basata su contesto incompleto. Monitora sempre la lunghezza dell'input in produzione.

## Riferimenti

- [OpenAI Tokenizer](https://platform.openai.com/tokenizer) — Visualizzatore interattivo di tokenizzazione
- [tiktoken GitHub](https://github.com/openai/tiktoken) — Libreria tokenizer OpenAI
- [Anthropic Token Counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — API per contare token con Claude
