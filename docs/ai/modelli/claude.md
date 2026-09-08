---
title: "Claude — Architettura, Capacità e API"
slug: claude
category: ai
tags: [claude, anthropic, constitutional-ai, rlhf, api, claude-code, context-window, multimodal]
search_keywords: [claude anthropic, claude api, claude 5, claude sonnet 5, claude opus 5, claude haiku 4.5, claude fable 5, constitutional ai, claude context window 1m, claude multimodal, claude computer use, claude artifacts, claude code, claude agent sdk, anthropic sdk, claude streaming, claude tool use, claude function calling, claude batch api, claude vision, claude pdf, claude prompt caching, adaptive thinking, extended thinking, reasoning effort, output_config effort]
parent: ai/modelli/_index
related: [ai/modelli/_index, ai/fondamentali/llm-architettura, ai/tokens-context/context-window, ai/agents/agent-patterns, ai/agents/claude-agent-sdk, ai/sviluppo/api-integration]
official_docs: https://docs.anthropic.com/
status: reviewed
difficulty: intermediate
last_updated: 2026-09-08
last_verified: 2026-09-08
---

# Claude — Architettura, Capacità e API

## Panoramica

**Claude** è la famiglia di modelli di Anthropic, sviluppata con un focus primario sulla safety, l'affidabilità e il comportamento utile. A differenza di altri LLM, Claude è stato progettato esplicitamente tramite **Constitutional AI (CAI)** — un approccio che usa principi espliciti e auto-revisione per allineare il modello invece di dipendere esclusivamente da labeling umano. Claude è oggi uno dei modelli più capaci per reasoning complesso, coding, analisi di documenti lunghi (fino a 1M token di context) e task agentici a lungo orizzonte.

Tutti i modelli correnti condividono lo stesso endpoint (`POST /v1/messages`), lo stesso SDK e — con poche eccezioni per tier — la stessa superficie di richiesta.

## Famiglia di Modelli Claude

### Generazioni

```
Claude 1 (2023)          Primo modello pubblico Anthropic
Claude 2 / 2.1 (2023)    Context 100K-200K, migliore instruction following
Claude 3 (2024)          Opus / Sonnet / Haiku — prima generazione multimodale
Claude 3.5 / 3.7 (2024-25) Sonnet 3.5/3.7, Haiku 3.5; Artifacts, Computer Use (beta), extended thinking
Claude 4 / 4.5 (2025)    Opus 4 / 4.1 / 4.5, Sonnet 4 / 4.5, Haiku 4.5; adaptive thinking, effort
Claude 4.6 / 4.7 / 4.8 (2025-26) Opus 4.6/4.7/4.8, Sonnet 4.6; prefill rimosso, context 1M, compaction
Claude 5 (2026)          Fable 5, Opus 5, Sonnet 5 — famiglia corrente; Haiku 4.5 resta il tier veloce
```

### Model ID Correnti (API)

I model ID della generazione corrente **non hanno suffisso di data**: si usa la stringa esatta.

| Model ID | Ruolo | Context | Input $/M | Output $/M |
|----------|-------|---------|-----------|------------|
| `claude-fable-5` | Massima capacità, reasoning e agentic a lungo orizzonte | 1M | $10 | $50 |
| `claude-opus-5` | Top tier per intelligenza e coding | 1M | $5 | $25 |
| `claude-sonnet-5` | Standard di produzione, ottimo rapporto qualità/costo | 1M | $2 | $10 |
| `claude-haiku-4-5` | Veloce ed economico, alto volume / bassa latenza | 200K | $1 | $5 |

Restano disponibili (non default): `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-sonnet-4-6`. Per un ID più vecchio consultare la [pagina modelli ufficiale](https://docs.anthropic.com/en/docs/about-claude/models/overview) — non costruirlo a mano.

!!! tip "Scelta del modello"
    Default per sviluppo e task agentici: **Opus 5**. Alto volume in produzione / RAG / classificazione: **Sonnet 5** o **Haiku 4.5**. Reasoning estremo o run autonomi lunghi: **Fable 5**. Vedi [Guida alla Scelta del Modello](scelta-modello.md).

## Constitutional AI — Come Claude è Allineato

L'allineamento di Claude differisce dagli altri LLM per l'uso di **Constitutional AI**:

### La Costituzione

Anthropic definisce una lista di principi (la "costituzione") che guidano il comportamento di Claude. Include principi da:

- Universal Declaration of Human Rights
- Principi propri di Anthropic su safety e onestà
- Linee guida per evitare danni, inganno e manipolazione

Esempi di principi:
> "Scegli la risposta che meno probabilmente aiuterebbe qualcuno a creare armi biologiche, chimiche, nucleari o radiologiche"
> "Scegli la risposta che è più onesta e non ingannevole in nessun modo"
> "Preferisci la risposta che è più rispettosa dell'autonomia e del libero arbitrio dell'utente"

### Pipeline CAI

```
1. CRITIQUE-REVISION LOOP (auto-miglioramento)
   Prompt problematico -> risposta iniziale -> "critica rispetto al principio X"
   -> critica -> "revisiona tenendo conto della critica" -> risposta revisionata (SL-CAI)

2. RLAIF (Reinforcement Learning from AI Feedback)
   Reward model addestrato su preferenze generate da AI (non solo umane)

3. RL TRAINING
   Ottimizzazione per massimizzare il reward rispettando i vincoli della costituzione
```

### HHH Framework

Claude è addestrato per essere **Helpful**, **Harmless**, **Honest**. Quando questi principi confliggono, l'ordine di priorità è: non causare danni gravi → onestà → utilità.

## Capacità Core

### Context Window

Fable 5, Opus 5 e Sonnet 5 hanno un context di **1.000.000 token** (~750.000 parole). Haiku 4.5 resta a **200K**. Il massimo è anche il default: non serve chiederlo.

```python
use_cases = {
    "Analisi codebase intera":      "Leggi molti file in un singolo prompt",
    "Conversazioni lunghe":         "Sessioni estese senza perdita di contesto",
    "RAG on-the-fly":               "Documenti direttamente nel prompt, senza vettorizzare",
    "Analisi log/trace":            "Trace di esecuzione complete per debugging",
}
```

!!! warning "Recency e primacy"
    Anche con 1M token, l'attenzione a inizio e fine contesto resta più alta. Metti le informazioni critiche all'inizio del system prompt o alla fine dell'ultimo messaggio utente. Per conversazioni che superano il context, usa la **compaction** server-side (beta `compact-2026-01-12`).

### Adaptive Thinking ed Effort

Il concetto di "thinking budget" a token fissi (`budget_tokens`) è **deprecato**. Sui modelli 4.6+ si usa il **thinking adattivo**: Claude decide da solo quando e quanto ragionare.

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16000,
    thinking={"type": "adaptive", "display": "summarized"},  # su Opus 5 il default è "omitted"
    output_config={"effort": "high"},  # low | medium | high | xhigh | max
    messages=[{"role": "user", "content": "Risolvi passo per passo..."}],
)

for block in response.content:
    if block.type == "thinking":
        print("Ragionamento:", block.thinking)
    elif block.type == "text":
        print("Risposta:", block.text)
```

| Punto | Comportamento corrente |
|---|---|
| `thinking` | `{type: "adaptive"}` su tutti i modelli correnti. Su Opus 5 il thinking è **on di default** (omettere il parametro equivale ad adaptive). |
| `budget_tokens` | Rimosso su Fable 5 / Opus 5 / Sonnet 5 e Opus 4.7/4.8 → **400 se inviato**. Deprecato (ma ancora funzionante) su Opus 4.6 / Sonnet 4.6. |
| `output_config.effort` | `low` \| `medium` \| `high` \| `xhigh` \| `max`. Default `high`. `xhigh` è il valore migliore per la maggior parte del coding e dell'agentic. Va **dentro** `output_config`, non top-level. |
| `display` | `"omitted"` (default su famiglia 5) = blocchi `thinking` vuoti; `"summarized"` = riassunto leggibile. La catena di pensiero grezza non è mai esposta. |
| `temperature` / `top_p` / `top_k` | **Rimossi** sui modelli 4.7+ (400 se inviati). |

### Multimodalità

```python
import anthropic, base64

client = anthropic.Anthropic()

with open("architecture.png", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=2048,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/png", "data": image_data}},
            {"type": "text", "text": "Identifica i single point of failure in questa architettura."},
        ],
    }],
)
```

**Immagini**: JPEG, PNG, GIF, WebP. Fino a ~20 immagini per messaggio.
**PDF nativi**: blocco `{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": ...}}` prima del blocco di testo. Limiti: 32 MB per richiesta, 600 pagine (100 sui modelli a 200K context). Per riuso su più richieste, caricare via **Files API** (beta `files-api-2025-04-14`) e referenziare con `source.type = "file"`.

### Tool Use (Function Calling)

```python
tools = [{
    "name": "execute_sql",
    "description": "Esegui una query su un database di sola lettura",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "database": {"type": "string", "enum": ["analytics", "production_ro"]},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "strict": True,   # top-level sulla tool def: garantisce che input validi lo schema
}]

response = client.messages.create(
    model="claude-opus-5", max_tokens=2048, tools=tools,
    messages=[{"role": "user", "content": "Quanti ordini oggi?"}],
)

if response.stop_reason == "tool_use":
    for block in response.content:
        if block.type == "tool_use":
            result = run_tool(block.name, block.input)   # sempre json.loads dell'input, mai match su stringa
            follow_up = client.messages.create(
                model="claude-opus-5", max_tokens=2048, tools=tools,
                messages=[
                    {"role": "user", "content": "Quanti ordini oggi?"},
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": block.id, "content": str(result)},
                    ]},
                ],
            )
```

Per più tool nella stessa risposta: eseguili in parallelo e restituisci **tutti** i `tool_result` in un **unico** messaggio user. Per l'agentic loop senza scrivere il ciclo a mano: SDK `client.beta.messages.tool_runner` (`@beta_tool` in Python).

### Output Strutturati

Usare `output_config: {format: {...}}` su `messages.create()` (il vecchio parametro `output_format` è deprecato). L'helper `client.messages.parse()` valida la risposta contro lo schema automaticamente.

### Prompt Caching

Riduce i costi fino a ~90% sulle parti ripetute (system prompt lungo, documenti RAG). È un **prefix match**: qualunque byte che cambia nel prefisso invalida tutto ciò che segue.

```python
response = client.messages.create(
    model="claude-opus-5", max_tokens=1024,
    system=[
        {"type": "text", "text": HANDBOOK_STATICO,
         "cache_control": {"type": "ephemeral"}},          # default TTL 5 min; "ttl": "1h" per 1 ora
        {"type": "text", "text": f"Data: {oggi}"},          # parte volatile DOPO il breakpoint
    ],
    messages=[{"role": "user", "content": domanda}],
)
print(response.usage.cache_read_input_tokens)  # se 0 su richieste ripetute -> invalidatore silenzioso
```

Ordine di render: `tools` → `system` → `messages`. Tenere stabile ciò che sta prima; timestamp e ID per-richiesta vanno dopo l'ultimo `cache_control`.

## Streaming

```python
with client.messages.stream(
    model="claude-opus-5", max_tokens=8000,
    messages=[{"role": "user", "content": "Analisi dettagliata di Kubernetes networking."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    final = stream.get_final_message()
```

Per `max_tokens` grandi (fino a 128K sui modelli 4.6+) lo streaming è **richiesto** dagli SDK per non incorrere nei timeout HTTP.

## Batch API

Elaborazione asincrona ad alto volume, ~50% di sconto:

```python
batch = client.messages.batches.create(requests=[
    {"custom_id": f"req-{i}", "params": {
        "model": "claude-sonnet-5", "max_tokens": 1024,
        "messages": [{"role": "user", "content": p}]}}
    for i, p in enumerate(prompts)
])
# poll batches.retrieve(batch.id).processing_status fino a "ended", poi batches.results(batch.id)
# i risultati arrivano in ordine qualsiasi: usa custom_id, non la posizione
```

## Server Tools

Tool che girano sull'infrastruttura Anthropic, dichiarati in `tools`; i risultati arrivano come content block nella stessa risposta.

| Tool | `type` corrente | Note |
|---|---|---|
| Web search | `web_search_20260209` | Filtraggio dinamico integrato; su modelli < 4.6 usare `web_search_20250305` |
| Web fetch | `web_fetch_20260209` | Fetcha solo URL già presenti nella conversazione |
| Code execution | `code_execution_20260521` | Result block `bash_code_execution_tool_result` (`.content.stdout`) |

## Computer Use

**Computer Use** permette a Claude di controllare un computer: mouse, tastiera, screenshot. È in beta e va usato con tool `computer_*` + il beta header corrispondente (le versioni datate del tool evolvono — vedi doc ufficiale).

!!! warning "Computer Use in produzione"
    Solo in sandbox isolate (VM, container). Claude può eseguire operazioni distruttive se istruito o manipolato via prompt injection.

## Claude Code e Agent SDK

**Claude Code** è il CLI/agent per lavorare su codebase (lettura file, esecuzione comandi, editing, coordinamento di task). È anche il motore dell'automazione di questa KB (`_automation/`).

**Claude Agent SDK** (`claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk`) è Claude Code impacchettato come libreria: tool integrati, loop dell'agente, gestione contesto, hook, subagent. È un prodotto **diverso** dal Tool Runner dell'SDK API. Vedi [Claude Agent SDK](../agents/claude-agent-sdk.md).

## Parametri Chiave dell'API

| Parametro | Note |
|-----------|------|
| `model` | obbligatorio; stringa ID esatta senza suffisso data |
| `max_tokens` | obbligatorio; default consigliato ~16000 (non-streaming), ~64000 (streaming) |
| `system` | string o lista di blocchi (per `cache_control`) |
| `thinking` | `{type: "adaptive"}` sui modelli correnti |
| `output_config` | `{effort: "...", format: {...}}` |
| `stream` | bool |
| `stop_sequences` | lista |
| `metadata.user_id` | per monitoring/abuse detection |

`temperature`, `top_p`, `top_k` e i prefill del messaggio assistant sono **rimossi** sui modelli 4.7+ (400).

## Rate Limits e Gestione Errori

L'SDK ritenta automaticamente 408/409/429/5xx con backoff (default `max_retries=2`). Retry custom solo se serve un comportamento diverso.

```python
import anthropic

try:
    response = client.messages.create(model="claude-opus-5", max_tokens=1024, messages=msgs)
except anthropic.RateLimitError as e:
    retry_after = int(e.response.headers.get("retry-after", "60"))
except anthropic.APIStatusError as e:
    if e.status_code == 529:      # Overloaded
        ...
    elif e.status_code >= 500:
        ...
    else:
        raise                    # 4xx non-retriabili (400 bad request, ecc.)
```

I limiti (RPM / ITPM / OTPM / RPD) scalano con il tier di spesa. Guardare sempre `response.stop_reason` prima di leggere `content`: su `"max_tokens"` la risposta è troncata (HTTP 200), su `"refusal"` è presente `stop_details`.

## Confronto Indicativo (2026)

I confronti fra provider invecchiano in fretta: usare fonti live come [Artificial Analysis](https://artificialanalysis.ai/) e [LMArena](https://lmarena.ai/) per numeri aggiornati.

| Aspetto | Claude (Sonnet 5 / Opus 5) | GPT (serie 5) | Gemini (serie 2.x/3) |
|---------|----------------------------|---------------|----------------------|
| Context window | 1M | grande (varia per modello) | 1M+ |
| Coding / agentic | eccellente | eccellente | forte |
| Instruction following | eccellente | forte | forte |
| Onestà / calibrazione | molto alta (CAI) | alta | media-alta |
| Computer use | sì (beta) | sì | limitato |
| Safety / Alignment | molto alto (Constitutional AI) | alto | medio-alto |

## Troubleshooting

### Scenario 1 — HTTP 529 "Overloaded" ricorrente

**Sintomo**: `APIStatusError: 529 Overloaded` persistente anche con retry.

**Causa**: cluster Anthropic sotto carico (fasce di picco, o Opus/Fable ad alto volume).

**Soluzione**: exponential backoff con jitter; passare temporaneamente a un tier inferiore; spostare il carico sulla Batch API (immune ai picchi sincroni).

```python
import random, time
from anthropic import APIStatusError

def call_with_backoff(client, **kwargs):
    for attempt in range(6):
        try:
            return client.messages.create(**kwargs)
        except APIStatusError as e:
            if e.status_code in (529, 503):
                time.sleep((2 ** attempt) + random.uniform(0, 1))
            else:
                raise
    raise RuntimeError("Max retries exceeded")
```

### Scenario 2 — `budget_tokens` restituisce 400

**Sintomo**: `BadRequestError` su una richiesta che imposta `thinking={"type": "enabled", "budget_tokens": N}`.

**Causa**: `budget_tokens` è rimosso su Fable 5 / Opus 5 / Sonnet 5 / Opus 4.7 / 4.8.

**Soluzione**: sostituire con thinking adattivo e controllare la profondità con l'effort.

```python
# prima (rotto sui modelli correnti)
# thinking = {"type": "enabled", "budget_tokens": 8000}

# dopo
response = client.messages.create(
    model="claude-opus-5", max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},   # "xhigh" per coding/agentic pesante
    messages=msgs,
)
```

### Scenario 3 — Risposta troncata (`stop_reason == "max_tokens"`)

**Sintomo**: la risposta si interrompe a metà frase/blocco; HTTP 200.

**Causa**: `max_tokens` inferiore alla lunghezza effettiva generata.

**Soluzione**: aumentare `max_tokens` (fino a 128K sui modelli 4.6+, ma serve `stream()`), oppure chiedere sintesi nel system prompt. Verificare sempre `stop_reason` prima di processare.

### Scenario 4 — Prefill dell'assistant restituisce 400

**Sintomo**: `BadRequestError` quando l'ultimo messaggio dell'array `messages` ha `role: "assistant"` per forzare l'inizio della risposta.

**Causa**: i prefill del messaggio assistant sono rimossi su Fable 5 / Opus 5 / Sonnet 5 e tutta la famiglia 4.6+.

**Soluzione**: usare gli **output strutturati** (`output_config.format`) o istruzioni nel system prompt per vincolare il formato.

### Scenario 5 — Prompt caching: cache miss inatteso

**Sintomo**: nonostante `cache_control`, i log mostrano sempre `cache_creation_input_tokens` e mai `cache_read_input_tokens`.

**Causa**: il contenuto marcato cambia tra le chiamate (timestamp/ID nel testo cachato, `json.dumps` non ordinato, tool set variabile), oppure sono passati più di 5 minuti (TTL scaduto).

**Soluzione**: il testo cachato deve essere byte-identico. Tenere ogni parte dinamica **dopo** l'ultimo `cache_control`. Monitorare `usage.cache_read_input_tokens`.

## Riferimenti

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude Model Overview](https://docs.anthropic.com/en/docs/about-claude/models/overview) — ID e capacità correnti
- [Constitutional AI Paper](https://arxiv.org/abs/2212.08073)
- [Extended Thinking Guide](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
- [Tool Use Guide](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Prompt Caching Guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Artificial Analysis](https://artificialanalysis.ai/) — benchmark indipendenti live
