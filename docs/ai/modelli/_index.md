---
title: "Modelli LLM"
slug: modelli-llm
category: ai
tags: [llm-models, claude, gpt, llama, mistral, gemini, benchmark]
search_keywords: [large language model, modelli linguistici, GPT-4, Claude, Llama, Mistral, Gemini, open weight, open source, closed source, MMLU, HumanEval, benchmark LLM, foundation model, modelli AI, API LLM]
parent: ai/_index
related: [ai/fondamentali/_index, ai/modelli/modelli-open-source, ai/modelli/scelta-modello, ai/tokens-context/_index, ai/sviluppo/prompt-engineering]
official_docs: https://artificialanalysis.ai/
status: complete
difficulty: beginner
last_updated: 2026-02-27
---

# Modelli LLM

## Panoramica

I Large Language Models (LLM) sono modelli neurali di dimensione massiccia — da miliardi a trilioni di parametri — addestrati su corpus testuali enormi con l'obiettivo di predire il token successivo in una sequenza. Da questo semplice obiettivo di training emergono capacità sorprendenti: reasoning, coding, analisi, traduzione, e generazione di testo coerente. Nel contesto DevOps, gli LLM sono strumenti pratici per generazione di IaC, analisi di log, code review, documentazione automatica e sistemi agentici.

Il panorama dei modelli si divide in due grandi famiglie: **closed** (accessibili solo tramite API, pesi non pubblici) e **open weight** (pesi scaricabili e deployabili autonomamente). La scelta tra le due dipende da requisiti di privacy, costo, latenza, e personalizzazione.

## Tassonomia dei Modelli

```
LLM
├── Closed (pesi non pubblici, solo API)
│   ├── Claude (Anthropic) — Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus
│   ├── GPT-4o, GPT-4o-mini (OpenAI)
│   ├── Gemini 1.5 Pro, Gemini 2.0 Flash (Google)
│   └── Grok (xAI)
├── Open Weight (pesi pubblici, licenza non sempre commerciale)
│   ├── Llama 3.x (Meta) — licenza Llama 3 (semi-open)
│   ├── Mistral / Mixtral (Mistral AI) — Apache 2.0 / licenza commerciale
│   ├── Gemma 2 (Google) — licenza Gemma
│   ├── Qwen 2.5 (Alibaba) — Apache 2.0
│   └── DeepSeek V3/R1 — licenza DeepSeek (aperta per ricerca)
└── Open Source (pesi + codice + dati)
    ├── OLMo (Allen AI)
    ├── Falcon (TII)
    └── BLOOM (BigScience)
```

## Panoramica Modelli — Tabella Comparativa

| Modello | Provider | Parametri | Context | Multimodal | Licenza | Ottimale per |
|---------|----------|-----------|---------|------------|---------|-------------|
| **Claude 3.5 Sonnet** | Anthropic | Non divulgato | 200K | Testo+Immagini | API | Coding, analisi, agentic tasks |
| **Claude 3.5 Haiku** | Anthropic | Non divulgato | 200K | Testo+Immagini | API | Velocità, costo, RAG |
| **Claude 3 Opus** | Anthropic | Non divulgato | 200K | Testo+Immagini | API | Task complessi, lunga catena di ragionamento |
| **GPT-4o** | OpenAI | Non divulgato | 128K | Testo+Img+Audio | API | Versatilità generale |
| **GPT-4o-mini** | OpenAI | Non divulgato | 128K | Testo+Immagini | API | Costo ridotto |
| **Gemini 1.5 Pro** | Google | Non divulgato | 1M | Testo+Img+Video | API | Context ultra-long, multimediale |
| **Gemini 2.0 Flash** | Google | Non divulgato | 1M | Testo+Img+Audio | API | Velocità, costo, real-time |
| **Llama 3.3 70B** | Meta | 70B | 128K | Testo | Llama 3 | Best open-weight per qualità |
| **Llama 3.2 3B** | Meta | 3B | 128K | Testo | Llama 3 | Edge deployment, on-device |
| **Mistral Large 2** | Mistral | ~123B | 128K | Testo | MRL | Alternativa API europea |
| **Mixtral 8×22B** | Mistral | 141B (attivi: 39B) | 64K | Testo | Apache 2.0 | MoE, buon rapporto qualità/costo |
| **Gemma 2 9B** | Google | 9B | 8K | Testo | Gemma | Deployment efficiente, on-device |
| **Qwen 2.5 72B** | Alibaba | 72B | 128K | Testo | Apache 2.0 | Coding, math, multilingual |
| **DeepSeek V3** | DeepSeek | 671B (attivi: 37B) | 128K | Testo | DeepSeek | Qualità GPT-4 level, open weight |
| **DeepSeek R1** | DeepSeek | 671B (attivi: 37B) | 128K | Testo | DeepSeek | Reasoning, matematica, coding |
| **Phi-4** | Microsoft | 14B | 16K | Testo | MIT | Small model, buona qualità |

## Benchmark Principali

I benchmark sono test standardizzati per misurare le capacità dei modelli. Attenzione: i benchmark possono essere "contaminati" (il modello ha visto i test durante il training).

| Benchmark | Cosa Misura | Formato | Punteggio Top (2025) |
|-----------|-------------|---------|---------------------|
| **MMLU** | Conoscenza su 57 domini accademici | Multiple choice, 0-shot/5-shot | ~90% (Claude 3 Opus, GPT-4) |
| **HumanEval** | Coding Python (pass@1) | Completamento funzione | ~90% (GPT-4o, Claude 3.5) |
| **MATH** | Problemi matematica competition | Risposta aperta | ~75-90% (modelli reasoning) |
| **GPQA** | Science livello PhD ("Google-Proof") | Multiple choice | ~60-70% |
| **MT-Bench** | Qualità conversazione multi-turn | Giudice GPT-4, 1-10 | ~9.0 (Claude 3.5, GPT-4o) |
| **LMSYS Arena** | ELO da preferenze umane | Confronto blind | Rankings live su lmsys.org |
| **BigBench Hard** | 23 task difficili (reasoning) | Vari | Ancora molto duro per tutti |
| **SWE-bench** | Fix di bug in repo GitHub reali | Pass/fail | ~50% (Claude 3.5 Sonnet) |

!!! note "Interpretazione benchmark"
    Un modello con MMLU 85% non è necessariamente migliore di uno con 82% per il tuo caso d'uso specifico. I benchmark generali non sostituiscono l'evaluation sul task reale. Per scegliere il modello, costruisci un eval set con i tuoi casi d'uso specifici.

## Architettura Generale degli LLM

Tutti i moderni LLM si basano sull'architettura **Transformer decoder-only**:

```
Input tokens
    ↓
Token Embedding + Positional Encoding (RoPE)
    ↓
[× N layer Transformer]
    ├── RMSNorm
    ├── Multi-Head Attention (con GQA / MQA per efficienza)
    ├── RMSNorm
    └── Feed-Forward Network (SwiGLU)
    ↓
Final RMSNorm
    ↓
LM Head (Linear → Softmax → next token probabilities)
```

**Innovazioni architetturali post-2023:**

| Innovazione | Descrizione | Modelli che la usano |
|-------------|-------------|---------------------|
| **GQA** (Grouped Query Attention) | Riduce KV cache. Query multiple, Key/Value condivisi in gruppi | Llama 3, Mistral |
| **MQA** (Multi-Query Attention) | GQA estremo: 1 solo gruppo K/V | Gemma, Falcon |
| **SwiGLU** | Attivazione FFN migliore di ReLU/GELU | Llama 3, Mistral, PaLM |
| **RoPE** (Rotary Position Embedding) | Encoding posizionale relativo, estendibile | Llama 3, Mistral |
| **RMSNorm** | Normalizzazione più semplice di LayerNorm | Llama 3, Mistral |
| **MoE** (Mixture of Experts) | Attiva solo un sottoinsieme di FFN per token | Mixtral, DeepSeek, Grok |
| **Flash Attention** | Implementazione attention IO-efficiente | Tutti i modelli moderni |

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Modelli Open Source / Open Weight**

    ---

    Llama 3, Mistral, Gemma, Qwen, DeepSeek. Deployment locale con Ollama e llama.cpp. Quantizzazione GGUF.

    [:octicons-arrow-right-24: Modelli Open Source](modelli-open-source.md)

-   **Guida alla Scelta del Modello**

    ---

    Framework decisionale per scegliere il modello giusto. Trade-off qualità/costo/latenza. Scenari DevOps tipici.

    [:octicons-arrow-right-24: Scelta Modello](scelta-modello.md)

</div>

## Riferimenti

- [LMSYS Chatbot Arena Leaderboard](https://chat.lmsys.org/?leaderboard) — ELO ranking da preferenze umane live
- [Artificial Analysis](https://artificialanalysis.ai/) — Benchmark indipendenti: qualità, velocità, costo
- [Open LLM Leaderboard (HuggingFace)](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) — Benchmark modelli open weight
- [Anthropic Model Documentation](https://docs.anthropic.com/en/docs/about-claude/models) — Modelli Claude disponibili
- [Llama 3 Model Card](https://github.com/meta-llama/llama3/blob/main/MODEL_CARD.md) — Dettagli Llama 3
