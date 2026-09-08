---
title: "Modelli LLM"
slug: modelli-llm
category: ai
tags: [llm-models, claude, gpt, llama, mistral, gemini, benchmark]
search_keywords: [large language model, modelli linguistici, GPT, Claude, Llama, Mistral, Gemini, DeepSeek, Qwen, open weight, open source, closed source, MMLU, HumanEval, SWE-bench, benchmark LLM, foundation model, modelli AI, API LLM, reasoning model]
parent: ai/_index
related: [ai/fondamentali/_index, ai/modelli/modelli-open-source, ai/modelli/scelta-modello, ai/tokens-context/_index, ai/sviluppo/prompt-engineering]
official_docs: https://artificialanalysis.ai/
status: reviewed
difficulty: beginner
last_updated: 2026-09-08
last_verified: 2026-09-08
---

# Modelli LLM

## Panoramica

I Large Language Models (LLM) sono modelli neurali di dimensione massiccia — da miliardi a trilioni di parametri — addestrati su corpus testuali enormi con l'obiettivo di predire il token successivo in una sequenza. Da questo semplice obiettivo di training emergono capacità sorprendenti: reasoning, coding, analisi, traduzione, e generazione di testo coerente. Nel contesto DevOps, gli LLM sono strumenti pratici per generazione di IaC, analisi di log, code review, documentazione automatica e sistemi agentici.

Il panorama dei modelli si divide in due grandi famiglie: **closed** (accessibili solo tramite API, pesi non pubblici) e **open weight** (pesi scaricabili e deployabili autonomamente). La scelta tra le due dipende da requisiti di privacy, costo, latenza, e personalizzazione.

## Tassonomia dei Modelli

```
LLM
├── Closed (pesi non pubblici, solo API)
│   ├── Claude (Anthropic) — famiglia 5: Fable 5, Opus 5, Sonnet 5; Haiku 4.5
│   ├── GPT (OpenAI) — serie 5 (+ varianti mini/nano), modelli reasoning "o-series"
│   ├── Gemini (Google) — serie 2.x / 3, Flash e Pro
│   └── Grok (xAI)
├── Open Weight (pesi pubblici, licenza non sempre commerciale)
│   ├── Llama (Meta) — Llama 3.x e 4 (licenza community Meta)
│   ├── Mistral / Mixtral (Mistral AI) — Apache 2.0 / licenza commerciale
│   ├── Gemma (Google) — licenza Gemma
│   ├── Qwen (Alibaba) — Qwen 2.5 / 3, Apache 2.0
│   └── DeepSeek V3 / R1 — licenza DeepSeek (MoE, reasoning)
└── Open Source (pesi + codice + dati)
    ├── OLMo (Allen AI)
    ├── Falcon (TII)
    └── BLOOM (BigScience)
```

!!! note "Nomi commerciali in movimento"
    Le versioni puntuali dei modelli closed cambiano di frequente. Per gli ID
    esatti e le capacità correnti dei modelli Claude vedi [Claude](claude.md) e la
    [pagina modelli Anthropic](https://docs.anthropic.com/en/docs/about-claude/models/overview);
    per il confronto cross-provider aggiornato usa [Artificial Analysis](https://artificialanalysis.ai/)
    e [LMArena](https://lmarena.ai/).

## Panoramica Modelli — Tabella Comparativa

> I modelli closed evolvono in fretta: la tabella indica il **posizionamento**, non l'ultima versione puntuale. Numeri live: [Artificial Analysis](https://artificialanalysis.ai/).

| Modello | Provider | Parametri | Context | Multimodal | Licenza | Ottimale per |
|---------|----------|-----------|---------|------------|---------|-------------|
| **Claude Opus 5** | Anthropic | Non divulgato | 1M | Testo+Immagini | API | Coding, agentic, reasoning complesso |
| **Claude Sonnet 5** | Anthropic | Non divulgato | 1M | Testo+Immagini | API | Produzione ad alto volume, analisi, RAG |
| **Claude Haiku 4.5** | Anthropic | Non divulgato | 200K | Testo+Immagini | API | Velocità, costo, classificazione |
| **Claude Fable 5** | Anthropic | Non divulgato | 1M | Testo+Immagini | API | Reasoning estremo, run autonomi lunghi |
| **GPT serie 5** | OpenAI | Non divulgato | grande | Testo+Img+Audio | API | Versatilità generale |
| **Gemini serie 2.x/3** | Google | Non divulgato | 1M+ | Testo+Img+Video | API | Context ultra-long, multimediale |
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

I punteggi assoluti invecchiano a ogni release: qui contano il **cosa misura** e l'ordine di grandezza. Numeri correnti: [Artificial Analysis](https://artificialanalysis.ai/), [LMArena](https://lmarena.ai/).

| Benchmark | Cosa Misura | Formato | Ordine di grandezza (frontier) |
|-----------|-------------|---------|--------------------------------|
| **MMLU / MMLU-Pro** | Conoscenza su decine di domini accademici | Multiple choice | frontier ~90% (MMLU), più basso su Pro |
| **HumanEval** | Coding Python (pass@1) | Completamento funzione | saturato (~95%+) — poco discriminante |
| **MATH** | Problemi matematica competition | Risposta aperta | alto per i modelli reasoning |
| **GPQA Diamond** | Science livello PhD ("Google-Proof") | Multiple choice | frontier ~70-85% |
| **LMArena** | ELO da preferenze umane | Confronto blind | ranking live |
| **SWE-bench Verified** | Fix di bug in repo GitHub reali | Pass/fail | frontier ~70-80% e in crescita |
| **Terminal-Bench / agentic** | Task multi-step in ambiente reale | Pass/fail | metrica chiave per l'uso agentico |

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
