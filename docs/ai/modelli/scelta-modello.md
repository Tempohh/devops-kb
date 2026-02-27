---
title: "Guida alla Scelta del Modello"
slug: scelta-modello
category: ai
tags: [model-selection, benchmark, cost, latency, use-case]
search_keywords: [scegliere modello AI, model selection, quale LLM usare, Claude vs GPT, open source vs closed, costo LLM, latenza LLM, privacy AI, on-premise AI, valutazione modelli, evals, use case AI DevOps, IaC generation AI, log analysis AI, incident analysis AI]
parent: ai/modelli/_index
related: [ai/modelli/_index, ai/modelli/modelli-open-source, ai/sviluppo/prompt-engineering, ai/training/valutazione]
official_docs: https://artificialanalysis.ai/
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# Guida alla Scelta del Modello

## Panoramica

La scelta del modello LLM giusto per un'applicazione non è una questione di "qual è il migliore in assoluto", ma di quale si adatta meglio al tuo specifico set di vincoli: tipo di task, requisiti di latenza, budget, conformità dei dati, e volume di richieste. Un modello frontier può essere eccessivo per una classificazione di log, mentre un modello piccolo può risultare inadeguato per analisi di incidenti complessi.

Questa guida fornisce un framework decisionale strutturato, non una risposta unica. Il processo corretto è: definire i requisiti → selezionare una shortlist → costruire un eval set rappresentativo → misurare → scegliere. Cambiare modello dopo il deployment è costoso; investire nella valutazione preventiva ripaga sempre.

## Framework Decisionale

### Step 1 — Definire i Requisiti

Prima di guardare i modelli, documenta i vincoli:

```
Vincoli da definire:
├── Task
│   ├── Tipo: generazione, classificazione, estrazione, coding, Q&A, reasoning
│   ├── Input: lunghezza media, tipo (codice, log, testo naturale, JSON)
│   └── Output: formato atteso (testo, JSON, codice, strutturato)
├── Performance
│   ├── Latenza massima accettabile (p99)
│   ├── Throughput (richieste/secondo)
│   └── Qualità minima accettabile (come la misuri?)
├── Costo
│   ├── Volume mensile (richieste o token)
│   └── Budget massimo per token o per mese
├── Privacy & Compliance
│   ├── I dati possono uscire dall'infrastruttura propria?
│   ├── Requisiti GDPR, HIPAA, SOC2?
│   └── Residenza dati (EU, US, on-premise)?
└── Operatività
    ├── Overhead operativo accettabile (managed API vs self-hosted)
    └── Competenze interne (ML engineering disponibile?)
```

### Step 2 — Decision Tree

```
Inizio
│
├── I dati sono sensibili/riservati?
│   ├── SÌ → On-premise obbligatorio
│   │         → Llama 3.x (70B per qualità, 8B per costo)
│   │         → Mistral / Mixtral (Apache 2.0)
│   │         → Qwen 2.5 (per coding/math)
│   └── NO → Continua
│
├── Il task è prevalentemente di coding?
│   ├── SÌ → Claude 3.5 Sonnet (migliore per SWE-bench)
│   │         → GPT-4o (alternativa)
│   │         → Qwen2.5-Coder (open, eccellente per coding)
│   └── NO → Continua
│
├── Richiede context molto lungo (>50K token)?
│   ├── SÌ → Claude 3.5 (200K context)
│   │         → Gemini 1.5 Pro / 2.0 (1M context)
│   └── NO → Continua
│
├── Task richiede reasoning complesso / matematica?
│   ├── SÌ → DeepSeek R1 / o1 (thinking models)
│   │         → Claude 3 Opus
│   └── NO → Continua
│
├── Latenza molto bassa richiesta (<500ms)?
│   ├── SÌ → Claude 3.5 Haiku / GPT-4o-mini / Gemini 2.0 Flash
│   │         → Open: Llama 3.2 3B su GPU locale
│   └── NO → Continua
│
├── Volume alto (>1M token/giorno) e budget limitato?
│   ├── SÌ → Self-hosted open weight (Llama 3.1 8B o 70B)
│   │         → Claude Haiku / GPT-4o-mini per API managed
│   └── NO → Continua
│
└── Task generico, nessun vincolo specifico
    └── → Claude 3.5 Sonnet (miglior balance qualità/costo)
        → GPT-4o (alternativa)
```

## Trade-off Matrix

| Dimensione | API Closed (Claude/GPT) | Open Weight (Llama/Mistral) |
|------------|------------------------|------------------------------|
| **Qualità** | Frontier (stato dell'arte) | Near-frontier (entro 10-20%) |
| **Costo per token** | Da $0.25/M a $15/M input | VRAM + compute (fisso) |
| **Costo a scala** | Cresce linearmente | Costante (infra fissa) |
| **Privacy** | Dati a terze parti | Controllo totale |
| **Latenza** | Variabile (rete) | Prevedibile (locale) |
| **Fine-tuning** | Limitato / non disponibile | Completo controllo |
| **Overhead operativo** | Zero | Alto (GPU, aggiornamenti) |
| **Compliance** | Dipende dalla regione | On-premise → compliance totale |
| **Aggiornamenti modello** | Automatici (può rompere behavior) | Controllati |

## Pricing dei Principali Modelli API (Febbraio 2026)

!!! warning "Prezzi soggetti a cambiamento"
    I prezzi cambiano frequentemente. Verificare sempre i prezzi aggiornati sui siti ufficiali.

| Modello | Input ($/M token) | Output ($/M token) | Note |
|---------|------------------|---------------------|------|
| Claude 3.5 Sonnet | $3.00 | $15.00 | Cache: $0.30/M |
| Claude 3.5 Haiku | $0.80 | $4.00 | Cache: $0.08/M |
| Claude 3 Opus | $15.00 | $75.00 | Task molto complessi |
| GPT-4o | $2.50 | $10.00 | |
| GPT-4o-mini | $0.15 | $0.60 | Economicissimo |
| Gemini 1.5 Pro | $1.25 | $5.00 | 1M context |
| Gemini 2.0 Flash | $0.10 | $0.40 | Molto veloce |
| Mistral Large | $2.00 | $6.00 | Alternativa EU |
| Mistral Nemo | $0.15 | $0.15 | Economico EU |

**Costo self-hosted (stima):**

| Modello | GPU Richiesta | Cloud ($/ora) | Token/s | Costo effettivo/M token |
|---------|-------------|---------------|---------|------------------------|
| Llama 3.1 8B Q4 | 1× RTX 4090 (24GB) | ~$0.5 | ~50 | ~$2.7 (con GPU cloud) |
| Llama 3.1 70B FP16 | 4× A100 80GB | ~$12 | ~20 | ~$83 |
| Mixtral 8×7B | 2× A100 40GB | ~$6 | ~30 | ~$55 |

!!! tip "Break-even self-hosted vs API"
    Il self-hosting è conveniente solo ad alto volume. Calcola: costo API mensile vs costo infra mensile. Tipicamente il break-even è intorno a 50-200M token/mese, dipende dal modello.

## Benchmark Interpretation

### Benchmark ≠ Performance sul Tuo Task

| Benchmark | Cosa misura | Rilevante se... |
|-----------|-------------|-----------------|
| **MMLU** | Conoscenza enciclopedica | Task di Q&A su knowledge base |
| **HumanEval** | Coding Python (funzioni singole) | Code generation task |
| **SWE-bench** | Fix bug in repo reali | Code agent, PR review |
| **MATH** | Matematica competition | Reasoning quantitativo |
| **GPQA** | Science livello PhD | Analisi tecnica avanzata |
| **MT-Bench** | Conversazione multi-turn | Chatbot, assistenti |
| **LMSYS Arena** | Preferenze umane generali | Task conversazionali generali |

!!! note "Costruisci i tuoi eval"
    I benchmark pubblici non sostituiscono l'evaluation sul tuo task specifico. Costruisci un set di 50-200 prompt rappresentativi dei tuoi casi d'uso reali, con golden answers, e usa quelli per scegliere il modello.

## Scenari Tipici DevOps

### Code Review Automatico

**Requisiti:** qualità alta, context fino a ~50K (PR grandi), latenza <30s, no dati sensibili preferito.

**Scelta:** Claude 3.5 Sonnet (migliore qualità su SWE-bench, segue istruzioni precise). Alternativa open: Qwen2.5-Coder 32B.

```python
# Esempio integrazione GitHub Actions
system_prompt = """Sei un senior software engineer. Analizza questa PR e fornisci:
1. Problemi di sicurezza (CRITICO)
2. Bug potenziali
3. Violazioni delle best practice
4. Suggerimenti di miglioramento
Formato: JSON con campi severity (critical/high/medium/low), description, line."""
```

### IaC Generation (Terraform, Kubernetes)

**Requisiti:** alta accuratezza sintattica, conoscenza provider cloud, output JSON/YAML strutturato.

**Scelta:** Claude 3.5 Sonnet o GPT-4o. Per on-premise: Llama 3.1 70B.

**Tip:** Poche righe di few-shot examples con esempi di output corretto riducono drasticamente gli errori sintattici.

### Log Analysis e Anomaly Detection

**Requisiti:** bassa latenza (idealmente <2s per alert), volume alto, pattern recognition.

**Scelta:**
- Per classificazione rapida: Claude 3.5 Haiku / GPT-4o-mini (veloce, economico)
- Per analisi root cause complessa: Claude 3.5 Sonnet
- Per on-premise ad alto volume: Llama 3.1 8B quantizzato

```python
# Pattern: prima classificazione veloce, poi analisi profonda se necessario
async def analyze_alert(alert_text: str) -> dict:
    # Step 1: classificazione rapida e economica
    severity = await classify_severity(alert_text, model="claude-haiku-3-5")

    if severity in ["critical", "high"]:
        # Step 2: analisi approfondita solo per alert importanti
        analysis = await deep_analyze(alert_text, model="claude-sonnet-3-5")
        return {"severity": severity, "analysis": analysis}

    return {"severity": severity, "analysis": None}
```

### Document Generation (Runbook, Post-mortem)

**Requisiti:** qualità output testuale, seguire template specifico, contesto lungo (log + metriche).

**Scelta:** Claude 3.5 Sonnet (eccellente per testo strutturato, segue template XML). Haiku per bozze, Sonnet per review finale.

### Incident Analysis Agent

**Requisiti:** reasoning multi-step, tool use, context lungo, qualità alta.

**Scelta:** Claude 3.5 Sonnet (miglior agentic performance), GPT-4o come alternativa. Open: Llama 3.1 70B per on-premise.

### Chatbot Interno su Documentazione

**Requisiti:** RAG su knowledge base interna, privacy (dati interni), volume medio.

**Scelta:**
- Se privacy critica: self-hosted Llama 3.1 8B o 70B + RAG locale (Qdrant)
- Se privacy non vincolante: Claude 3.5 Haiku (economico, veloce) + RAG

## Valutazione Sistematica

### Come Costruire un Eval Set

```python
# Struttura di un eval set per code review
eval_dataset = [
    {
        "id": "eval-001",
        "input": {
            "system": "Sei un code reviewer senior...",
            "user": "Review questo codice Python:\n```python\n...\n```"
        },
        "golden": {
            "must_mention": ["SQL injection", "parametrized query"],
            "must_not_mention": [],
            "severity_expected": "critical"
        },
        "tags": ["security", "python", "sql"]
    },
    # ... altri esempi
]

# Valutazione con LLM-as-Judge
async def evaluate_response(response: str, golden: dict, judge_model: str) -> dict:
    judge_prompt = f"""
    Valuta questa risposta di code review su scala 1-5.

    Criteri:
    - Identifica tutti i problemi critici di sicurezza: {golden['must_mention']}
    - Non genera falsi positivi
    - Fornisce suggerimenti pratici

    Risposta da valutare:
    {response}

    Output JSON: {{"score": 1-5, "reasoning": "...", "missed_issues": []}}
    """
    # ...
```

### Framework di Valutazione

```bash
# promptfoo: eval framework open source
npm install -g promptfoo

# promptfooconfig.yaml
providers:
  - id: anthropic:claude-3-5-sonnet-20241022
  - id: openai:gpt-4o
  - id: ollama:llama3.1:70b

prompts:
  - file://prompts/code-review.txt

tests:
  - file://evals/code-review-tests.yaml

# Esecuzione
promptfoo eval
promptfoo view  # UI comparativa
```

## Anti-Pattern Comuni

- **Scegliere il modello "migliore" senza definire "migliore per cosa"**: il modello top su MMLU può essere peggiore su SWE-bench.
- **Non considerare i costi a scala**: un modello 5× più costoso ma 10% migliore può non valere l'investimento.
- **Ignorare la latenza**: un modello con 30s di latenza è inutilizzabile in una pipeline utente-facing.
- **Non valutare su dati propri**: i benchmark pubblici non riflettono la distribuzione del tuo task.
- **Lock-in su un singolo provider**: costruisci un'astrazione (LiteLLM, Gateway) che permette di cambiare modello.
- **Sottovalutare il prompt engineering**: spesso migliorare il prompt dà più benefici che passare a un modello più grande.

## Riferimenti

- [Artificial Analysis](https://artificialanalysis.ai/) — Benchmark indipendenti qualità/velocità/costo
- [LMSYS Chatbot Arena](https://chat.lmsys.org/?leaderboard) — ELO umano live
- [promptfoo](https://promptfoo.dev/) — Framework eval open source
- [LiteLLM](https://litellm.ai/) — Proxy unificato per tutti i provider LLM
- [Anthropic Model Pricing](https://www.anthropic.com/pricing) — Prezzi aggiornati Claude
