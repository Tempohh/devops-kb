---
title: "Sviluppo Applicazioni AI"
slug: sviluppo-ai
category: ai
tags: [development, api, rag, prompt-engineering]
search_keywords: [sviluppo applicazioni AI, AI development, LLM API, integrazione LLM, RAG application, prompt engineering, SDK Anthropic, openai python, chatbot development, AI DevOps tools, LLM production, API LLM Python]
parent: ai/_index
related: [ai/modelli/_index, ai/tokens-context/_index, ai/agents/_index, ai/mlops/_index]
official_docs: https://docs.anthropic.com/en/api/getting-started
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# Sviluppo Applicazioni AI

## Panoramica

Integrare un LLM in un'applicazione richiede molto più che una chiamata API. Lo stack di sviluppo AI include: scelta del modello, progettazione del prompt, gestione del contesto, retrieval di dati rilevanti (RAG), orchestrazione del flusso, gestione degli errori, e monitoring in produzione. Ogni livello ha le sue best practice e i suoi anti-pattern.

In ambito DevOps, le applicazioni AI più comuni sono: code review assistant, chatbot su documentazione interna, analisi di log e alert, generazione di IaC da descrizioni naturali, post-mortem automatici, e agenti per automazione. Tutte queste applicazioni condividono gli stessi building block fondamentali: un buon prompt, il retrieval del contesto giusto, e un'integrazione robusta con i sistemi esistenti.

## Stack Applicazione AI Tipico

```
┌─────────────────────────────────────────────────────────┐
│                    Applicazione AI                       │
│                                                          │
│  ┌─────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  User   │  │   Gateway /  │  │    Monitoring      │  │
│  │Interface│  │  Rate Limit  │  │ LangFuse/Helicone  │  │
│  └────┬────┘  └──────┬───────┘  └────────────────────┘  │
│       │              │                                   │
│  ┌────▼──────────────▼────────────────────────────────┐  │
│  │               Orchestration Layer                  │  │
│  │  Prompt Engineering + Context Management           │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │                  RAG Pipeline                      │  │
│  │  Query → Embed → Retrieve → Rerank → Augment       │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │                   LLM API                          │  │
│  │  Claude / GPT-4o / Llama (self-hosted)             │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Integrazione Base con Claude SDK

```python
import anthropic
from typing import Iterator

client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY da env

# Chiamata semplice
def ask_claude(question: str, system: str = None) -> str:
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system=system or "Sei un assistente tecnico esperto.",
        messages=[{"role": "user", "content": question}]
    )
    return response.content[0].text

# Streaming
def stream_claude(question: str) -> Iterator[str]:
    with client.messages.stream(
        model="claude-3-5-haiku-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": question}]
    ) as stream:
        for text in stream.text_stream:
            yield text

# Conversazione multi-turn
def chat(messages: list[dict], system: str = None) -> str:
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        system=system,
        messages=messages
    )
    return response.content[0].text

# Esempio conversazione
conversation = []
conversation.append({"role": "user", "content": "Cos'è un Kubernetes Operator?"})
response1 = chat(conversation, "Sei un esperto Kubernetes.")
conversation.append({"role": "assistant", "content": response1})
conversation.append({"role": "user", "content": "Puoi farmi un esempio concreto?"})
response2 = chat(conversation, "Sei un esperto Kubernetes.")
```

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Prompt Engineering**

    ---

    Tecniche zero-shot, few-shot, chain-of-thought, tree of thoughts, meta-prompting. System prompt design. Testing e versioning.

    [:octicons-arrow-right-24: Prompt Engineering](prompt-engineering.md)

-   **RAG — Retrieval-Augmented Generation**

    ---

    Architettura RAG completa. Chunking, embedding, vector database (Qdrant, Pinecone, pgvector). Advanced RAG: reranking, HyDE, hybrid search.

    [:octicons-arrow-right-24: RAG](rag.md)

</div>

## Pattern Comuni in Produzione

### Retry con Exponential Backoff

```python
import time
import anthropic

client = anthropic.Anthropic()

def call_with_retry(prompt: str, max_retries: int = 3, base_delay: float = 1.0) -> str:
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
        except anthropic.APIError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay)
    return ""
```

### Output Strutturato (JSON)

```python
import json
from pydantic import BaseModel

class IncidentAnalysis(BaseModel):
    severity: str
    root_cause: str
    affected_services: list[str]
    remediation_steps: list[str]
    estimated_recovery_time: str

def analyze_incident_structured(incident_description: str) -> IncidentAnalysis:
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system="Rispondi SOLO con JSON valido, nessun testo aggiuntivo.",
        messages=[{
            "role": "user",
            "content": f"""Analizza questo incidente e rispondi con JSON:
{{
  "severity": "P1|P2|P3|P4",
  "root_cause": "...",
  "affected_services": ["..."],
  "remediation_steps": ["..."],
  "estimated_recovery_time": "..."
}}

Incidente: {incident_description}"""
        }]
    )
    return IncidentAnalysis(**json.loads(response.content[0].text))
```

## Riferimenti

- [Anthropic API Documentation](https://docs.anthropic.com/en/api/) — Documentazione completa API
- [anthropic-sdk-python](https://github.com/anthropic-ai/anthropic-sdk-python) — SDK Python ufficiale
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook) — Esempi pratici e pattern
- [OpenAI Cookbook](https://cookbook.openai.com/) — Pattern e best practice (molti applicabili a Claude)
