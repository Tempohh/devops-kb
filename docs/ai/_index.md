---
title: "Intelligenza Artificiale & LLM"
slug: ai
category: ai
tags: [ai, llm, machine-learning, deep-learning, agents, mlops]
search_keywords: [artificial intelligence, large language models, machine learning, deep learning, neural networks, transformer, claude, gpt, llama, agents, mlops, fine-tuning, rag, prompt engineering]
parent: null
related: [ci-cd/_index, containers/kubernetes/_index, security/_index]
official_docs: https://docs.anthropic.com/
status: complete
difficulty: beginner
last_updated: 2026-02-27
---

# Intelligenza Artificiale & LLM

## Panoramica

L'Intelligenza Artificiale moderna — in particolare i **Large Language Models (LLM)** — rappresenta una delle trasformazioni più profonde nell'ingegneria del software degli ultimi decenni. Comprendere come funzionano questi sistemi, come integrarli nelle applicazioni, e come operarli in produzione è diventato un requisito fondamentale per chi lavora in ambito DevOps, platform engineering e sviluppo software.

Questa sezione copre l'intero spettro: dalle fondamenta matematiche del Machine Learning, all'architettura dei Transformer, al funzionamento specifico di Claude, fino ai pattern di deployment e MLOps in contesti enterprise.

## Mappa della Conoscenza

```
Livello 1 — Fondamentali
│
├── Machine Learning         → Paradigmi, algoritmi, training loop
├── Deep Learning            → Reti neurali, backpropagation, architetture
└── Architettura LLM         → Transformer, Attention, Tokenization, Pre-training

Livello 2 — Modelli e Capacità
│
├── Claude                   → Constitutional AI, RLHF, capacità, API
├── Modelli Open Source      → Llama, Mistral, Gemma, Qwen, deployment
└── Scelta del Modello       → Benchmark, trade-off, caso d'uso

Livello 3 — Tokens e Contesto
│
├── Tokenizzazione           → BPE, vocab, costo token, multilingual
└── Context Window           → KV Cache, long context, strategie

Livello 4 — Agenti e Automazione
│
├── Agent Patterns           → ReAct, Tool Use, Multi-Agent, CoT
├── Claude Agent SDK         → Claude Code, orchestrazione
└── Frameworks               → LangChain, LlamaIndex, AutoGen, CrewAI

Livello 5 — Sviluppo Applicativo
│
├── API Integration          → Anthropic API, streaming, batch, function calling
├── Prompt Engineering       → System prompts, few-shot, CoT, template patterns
└── RAG                      → Vector DB, chunking, retrieval, reranking

Livello 6 — Training e Valutazione
│
├── Fine-Tuning              → LoRA, QLoRA, RLHF, RLAIF, DPO
└── Valutazione              → MMLU, HumanEval, evals custom, benchmarks

Livello 7 — MLOps
│
├── Infrastruttura GPU       → CUDA, cluster, VRAM planning
├── Model Serving            → vLLM, TGI, Triton, SLA, auto-scaling
└── Pipeline ML              → Experiment tracking, feature store, monitoring
```

## Perché Conta per il DevOps

L'AI in un contesto DevOps ha tre livelli di rilevanza crescente:

**1. Utilizzare AI nei tool (AI-augmented DevOps)**
- GitHub Copilot, Claude Code, Cursor per accelerare lo sviluppo
- AI per analisi di log, alert correlation, anomaly detection
- AI-assisted code review e documentation

**2. Integrare LLM nelle applicazioni (AI-powered applications)**
- Chatbot, sistemi di Q&A su documentazione interna
- Automazione di task complessi via agenti
- RAG su knowledge base aziendale

**3. Operare LLM in produzione (MLOps)**
- Deployment di modelli su GPU cluster (on-prem o cloud)
- Serving ad alta disponibilità con vLLM/TGI
- Monitoring, drift detection, cost optimization

## Timeline LLM

| Anno | Evento |
|------|--------|
| 2017 | Paper "Attention Is All You Need" — nasce l'architettura Transformer |
| 2018 | BERT (Google) — pre-training + fine-tuning diventa standard |
| 2020 | GPT-3 (OpenAI) — 175B parametri, emergent capabilities |
| 2022 | InstructGPT — RLHF per allineamento; ChatGPT (nov 2022) |
| 2023 | GPT-4, Claude 2, Llama 2 (Meta open source), Mistral 7B |
| 2024 | Claude 3 (Opus/Sonnet/Haiku), Llama 3, Gemini 1.5 (1M context), GPT-4o |
| 2025 | Claude 3.5/4, Llama 3.3, DeepSeek R1, reasoning models (o1/o3) |
| 2026 | Claude 4.5/4.6, multimodal nativo, agentic workflows mainstream |

## Glossario Rapido

| Termine | Definizione |
|---------|-------------|
| **LLM** | Large Language Model — modello con miliardi di parametri trainato su testo |
| **Token** | Unità di testo (parola, sub-word, carattere) — unità di input/output dei LLM |
| **Context Window** | Numero massimo di token che il modello può "vedere" in un'unica chiamata |
| **Transformer** | Architettura neurale basata su attention — backbone di tutti i LLM moderni |
| **Attention** | Meccanismo che permette al modello di pesare la rilevanza tra parti diverse del testo |
| **RLHF** | Reinforcement Learning from Human Feedback — tecnica di allineamento |
| **Fine-tuning** | Addestrare un modello pre-trained su dati specifici per un task |
| **RAG** | Retrieval-Augmented Generation — arricchire il contesto con documenti recuperati |
| **Agent** | Sistema in cui un LLM può usare tool, pianificare e agire autonomamente |
| **Inference** | Esecuzione del modello per generare output (opposto di training) |
| **Quantization** | Riduzione della precisione numerica dei pesi per ridurre VRAM/latenza |
| **LoRA** | Low-Rank Adaptation — tecnica efficiente di fine-tuning |

## Sezioni

<div class="grid cards" markdown>

-   :material-school:{ .lg .middle } **Fondamentali**

    ---

    Machine Learning, Deep Learning, e l'architettura Transformer che è alla base di tutti i moderni LLM.

    [:octicons-arrow-right-24: Fondamentali](fondamentali/_index.md)

-   :material-robot:{ .lg .middle } **Modelli**

    ---

    Claude, GPT, modelli open source. Come scegliere il modello giusto per il proprio caso d'uso.

    [:octicons-arrow-right-24: Modelli](modelli/_index.md)

-   :material-counter:{ .lg .middle } **Tokens & Context**

    ---

    Tokenizzazione BPE, gestione del context window, KV Cache, strategie per contesti lunghi.

    [:octicons-arrow-right-24: Tokens & Context](tokens-context/_index.md)

-   :material-sitemap:{ .lg .middle } **Agenti**

    ---

    Pattern agentici, ReAct, tool use, multi-agent systems, Claude Agent SDK, LangChain.

    [:octicons-arrow-right-24: Agenti](agents/_index.md)

-   :material-code-braces:{ .lg .middle } **Sviluppo**

    ---

    API integration, prompt engineering avanzato, RAG con vector database.

    [:octicons-arrow-right-24: Sviluppo](sviluppo/_index.md)

-   :material-tune:{ .lg .middle } **Training**

    ---

    Fine-tuning, LoRA, QLoRA, RLHF, DPO, valutazione e benchmark.

    [:octicons-arrow-right-24: Training](training/_index.md)

-   :material-server:{ .lg .middle } **MLOps**

    ---

    GPU infrastructure, model serving con vLLM/TGI, pipeline ML, monitoring.

    [:octicons-arrow-right-24: MLOps](mlops/_index.md)

</div>
