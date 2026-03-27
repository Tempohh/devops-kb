---
title: "Claude — Architettura, Capacità e API"
slug: claude
category: ai
tags: [claude, anthropic, constitutional-ai, rlhf, api, claude-code, context-window, multimodal]
search_keywords: [claude anthropic, claude api, claude 3, claude 3.5, claude 4, claude sonnet, claude opus, claude haiku, constitutional ai, claude context window 200k, claude multimodal, claude computer use, claude artifacts, claude code, claude agent sdk, anthropic sdk, claude streaming, claude tool use, claude function calling, claude batch api, claude vision, claude pdf, claude prompt caching]
parent: ai/modelli/_index
related: [ai/modelli/_index, ai/fondamentali/llm-architettura, ai/tokens-context/context-window, ai/agents/agent-patterns, ai/agents/claude-agent-sdk, ai/sviluppo/api-integration]
official_docs: https://docs.anthropic.com/
status: complete
difficulty: intermediate
last_updated: 2026-03-27
---

# Claude — Architettura, Capacità e API

## Panoramica

**Claude** è la famiglia di modelli di Anthropic, sviluppata con un focus primario sulla safety, l'affidabilità e il comportamento utile. A differenza di altri LLM, Claude è stato progettato esplicitamente tramite **Constitutional AI (CAI)** — un approccio che usa principi espliciti e auto-revisione per allineare il modello invece di dipendere esclusivamente da labeling umano. Claude è oggi uno dei modelli più capaci per reasoning complesso, coding, analisi di documenti lunghi (200K token di context), scrittura e task agentici.

## Famiglia di Modelli Claude

### Generazioni

```
Claude 1 (2023)
│   └── Primo modello pubblico Anthropic
│
Claude 2 / 2.1 (2023)
│   ├── Context window 100K-200K (rivoluzionario per l'epoca)
│   └── Miglioramento following istruzioni
│
Claude 3 (2024)
│   ├── Opus   — massima capacità, multimodal
│   ├── Sonnet — bilanciamento capacità/velocità
│   └── Haiku  — velocissimo, economico
│
Claude 3.5 (2024)
│   ├── Sonnet 3.5 — supera Claude 3 Opus su molti benchmark
│   ├── Haiku 3.5  — upgrade significativo di velocità/qualità
│   └── Artifacts feature, Computer Use (beta)
│
Claude 4 / 4.5 / 4.6 (2025-2026)
    ├── Opus 4.6    — massima capacità, reasoning avanzato
    ├── Sonnet 4.6  — modello corrente production-grade
    └── Haiku 4.5   — velocità ottimizzata, basso costo
```

### Model IDs Correnti (API)

| Model ID | Descrizione | Context | Input $/M | Output $/M |
|----------|-------------|---------|-----------|------------|
| `claude-opus-4-6` | Massima capacità | 200K | $15 | $75 |
| `claude-sonnet-4-6` | Production standard | 200K | $3 | $15 |
| `claude-haiku-4-5-20251001` | Veloce/economico | 200K | $0.25 | $1.25 |

!!! tip "Scelta del modello"
    Per la maggior parte dei task di sviluppo: **Sonnet 4.6**. Per task che richiedono massimo ragionamento: **Opus 4.6**. Per inferenza ad alto volume e bassa latenza: **Haiku 4.5**.

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
   ┌─────────────────────────────────────────────┐
   │  Prompt potenzialmente problematico         │
   │           ↓                                 │
   │  Risposta iniziale del modello              │
   │           ↓                                 │
   │  "Critica questa risposta rispetto al       │
   │   principio X della costituzione"          │
   │           ↓                                 │
   │  Critica generata                           │
   │           ↓                                 │
   │  "Revisiona la risposta tenendo conto       │
   │   della critica"                           │
   │           ↓                                 │
   │  Risposta revisionata (SL-CAI data)         │
   └─────────────────────────────────────────────┘

2. RLAIF (Reinforcement Learning from AI Feedback)
   Reward model addestrato su preferenze generate da AI
   (invece che esclusivamente da umani)

3. RL TRAINING
   Claude viene ottimizzato per massimizzare il reward
   rispettando i vincoli della costituzione
```

### HHH Framework

Claude è addestrato per essere:
- **Helpful** (Utile): massimizzare il valore reale per l'utente e la società
- **Harmless** (Non dannoso): evitare output che causano danni
- **Honest** (Onesto): non ingannare, calibrare l'incertezza, non manipolare

Quando questi principi sono in conflitto, Claude prioritizza in questo ordine: non causare danni gravi → onestà → utilità.

## Capacità Core di Claude

### Context Window 200K

Claude supporta **200.000 token** di context (~150.000 parole, ~500 pagine). Questo permette di:

```python
# Esempi di utilizzo del long context
use_cases = {
    "Analisi documenti interi": "Leggi un intero codebase, report, o libro in un singolo prompt",
    "Multi-turn conversation lunghe": "Sessioni di lavoro estese senza perdita di contesto",
    "RAG on-the-fly": "Inserire direttamente documenti nel prompt invece di vettorizzare",
    "Analisi log/trace": "Passare trace di esecuzione o log completi per debugging",
    "Code review intero repository": "Analizzare coerenza e pattern su molti file",
}
```

!!! warning "Needle in a Haystack"
    La qualità del retrieval degrada con contesti molto lunghi — Claude mantiene alta attenzione alle prime e ultime parti del contesto (primacy e recency effect). Per informazioni critiche, posizionarle all'inizio del system prompt o alla fine del messaggio utente.

### Multimodalità

Claude 3+ supporta **input visivi**:

```python
import anthropic
import base64

client = anthropic.Anthropic()

# Immagine da URL
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": "https://example.com/diagram.png"
                }
            },
            {
                "type": "text",
                "text": "Analizza questo diagramma di architettura e identifica i potential single points of failure."
            }
        ]
    }]
)

# Immagine in base64 (file locale)
with open("architecture.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_data
                }
            },
            {"type": "text", "text": "Descrivi l'architettura mostrata."}
        ]
    }]
)
```

**Formati supportati**: JPEG, PNG, GIF, WebP. Max ~5MB per immagine. Fino a 20 immagini per messaggio.

**PDF nativi** (Claude 3.5+): Claude può leggere direttamente PDF senza estrazione testo:

```python
with open("technical-spec.pdf", "rb") as f:
    pdf_data = base64.b64encode(f.read()).decode("utf-8")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_data
                }
            },
            {"type": "text", "text": "Riassumi i requisiti tecnici principali."}
        ]
    }]
)
```

### Tool Use (Function Calling)

Claude può usare **tool** (funzioni esterne) in modo strutturato:

```python
tools = [
    {
        "name": "get_weather",
        "description": "Ottieni il meteo corrente per una città",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nome della città"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Unità di misura"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "execute_sql",
        "description": "Esegui una query SQL su un database di sola lettura",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query SQL da eseguire"},
                "database": {"type": "string", "enum": ["analytics", "production_ro"]}
            },
            "required": ["query"]
        }
    }
]

# Messaggio iniziale
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{
        "role": "user",
        "content": "Che tempo fa a Roma? E quanti ordini abbiamo avuto oggi?"
    }]
)

# Claude risponde con tool_use blocks
# response.stop_reason == "tool_use"
tool_calls = [b for b in response.content if b.type == "tool_use"]

for tool_call in tool_calls:
    print(f"Tool: {tool_call.name}, Input: {tool_call.input}")

# Esegui i tool e restituisci i risultati
tool_results = []
for tool_call in tool_calls:
    if tool_call.name == "get_weather":
        result = call_weather_api(tool_call.input["city"])
    elif tool_call.name == "execute_sql":
        result = execute_db_query(tool_call.input["query"])

    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tool_call.id,
        "content": str(result)
    })

# Secondo turno: Claude usa i risultati per rispondere
final_response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[
        {"role": "user", "content": "Che tempo fa a Roma? E quanti ordini abbiamo avuto oggi?"},
        {"role": "assistant", "content": response.content},  # risposta con tool_use
        {"role": "user", "content": tool_results}            # risultati tool
    ]
)
```

### Prompt Caching

Il **prompt caching** riduce i costi fino al 90% per prompt con parti ripetute (system prompt lungo, documenti RAG, ecc.):

```python
# Marca le sezioni da cachare con cache_control
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "Sei un esperto di sicurezza cloud."
        },
        {
            "type": "text",
            "text": open("security-handbook-300pages.txt").read(),
            "cache_control": {"type": "ephemeral"}  # cacheato per 5 minuti
        }
    ],
    messages=[{"role": "user", "content": domanda}]
)

# Costo:
# Prima chiamata: full price per la parte cachata + normale per il resto
# Chiamate successive (entro 5 min): 90% sconto sulla parte cachata
# Read cache hit: $0.30/M token (vs $3/M per Sonnet 4.6)
```

## Streaming

Per applicazioni interattive, lo streaming riduce la latency percepita:

```python
# Streaming via context manager
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[{"role": "user", "content": "Scrivi un'analisi dettagliata di Kubernetes."}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# Stream con eventi completi (per tool use in streaming)
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Controlla il meteo di Milano"}]
) as stream:
    for event in stream:
        if event.type == "content_block_start":
            print(f"\nNuovo block: {event.content_block.type}")
        elif event.type == "content_block_delta":
            if hasattr(event.delta, "text"):
                print(event.delta.text, end="", flush=True)
```

## Batch API

Per elaborazione asincrona ad alto volume (fino al 50% di sconto):

```python
# Crea un batch di richieste
batch = client.beta.messages.batches.create(
    requests=[
        {
            "custom_id": f"request-{i}",
            "params": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            }
        }
        for i, prompt in enumerate(prompts_list)
    ]
)

print(f"Batch ID: {batch.id}, Status: {batch.processing_status}")

# Poll finché non è completato (tipicamente minuti-ore)
import time
while True:
    batch_status = client.beta.messages.batches.retrieve(batch.id)
    if batch_status.processing_status == "ended":
        break
    time.sleep(30)

# Recupera risultati
for result in client.beta.messages.batches.results(batch.id):
    if result.result.type == "succeeded":
        print(f"{result.custom_id}: {result.result.message.content[0].text[:100]}")
    else:
        print(f"{result.custom_id}: ERRORE — {result.result.error}")
```

## Computer Use (Claude 3.5+)

**Computer Use** permette a Claude di controllare un computer reale: muovere il mouse, cliccare, digitare, prendere screenshot. È progettato per automazione GUI e agent task complessi.

```python
# Computer Use tools
computer_tools = [
    {
        "type": "computer_20241022",
        "name": "computer",
        "display_width_px": 1920,
        "display_height_px": 1080,
        "display_number": 1
    },
    {
        "type": "bash_20241022",
        "name": "bash"
    },
    {
        "type": "text_editor_20241022",
        "name": "str_replace_editor"
    }
]

response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    tools=computer_tools,
    messages=[{
        "role": "user",
        "content": "Apri il browser, vai su github.com e controlla le ultime PR aperte del repository 'my-org/my-repo'"
    }],
    betas=["computer-use-2024-10-22"]
)
```

!!! warning "Computer Use in produzione"
    Computer Use è potente ma richiede sandbox isolate (VM, container) per sicurezza. Non eseguire mai in ambiente prod non isolato — Claude può fare operazioni distruttive se istruito (o manipolato via prompt injection).

## Claude Code e Agent SDK

**Claude Code** è il CLI che stai usando ora — un agente AI che può leggere file, eseguire comandi, scrivere codice, navigare codebase, e coordinare task complessi.

**Claude Agent SDK** è il framework per costruire agenti custom con Claude come LLM sottostante. Vedi [Claude Agent SDK](../agents/claude-agent-sdk.md) per dettagli completi.

## Parametri Chiave dell'API

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `model` | string | — | ID modello (obbligatorio) |
| `max_tokens` | int | — | Max token output (obbligatorio) |
| `temperature` | float | 1.0 | 0=deterministico, 1=default, >1=creativo |
| `top_p` | float | 1.0 | Nucleus sampling — alternativa a temperature |
| `top_k` | int | — | Top-k sampling |
| `stop_sequences` | list[str] | [] | Ferma la generazione a questi token |
| `system` | str/list | — | System prompt |
| `stream` | bool | false | Abilita streaming |
| `metadata.user_id` | str | — | ID utente per monitoring/abuse detection |

### Temperature — Guida Pratica

```python
# temperature=0: output deterministico (stesso input → stesso output)
# Usare per: JSON extraction, classification, code generation precisa
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=256,
    temperature=0,
    messages=[{"role": "user", "content": "Estrai i dati JSON da questo testo: ..."}]
)

# temperature=0.7: bilanciamento (default raccomandato per chat)
# Usare per: Q&A, assistenza, analisi

# temperature=1.0 (default Anthropic): comportamento standard

# temperature>1: più casuale e creativo
# Usare per: brainstorming, poetry, varietà nelle risposte
```

## Rate Limits e Gestione Errori

```python
import anthropic
import time
from anthropic import RateLimitError, APIStatusError

client = anthropic.Anthropic()

def robust_api_call(messages, max_retries=5):
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            return client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=messages
            )

        except RateLimitError as e:
            # HTTP 429 — rate limit raggiunto
            retry_after = int(e.response.headers.get("retry-after", base_delay * (2 ** attempt)))
            print(f"Rate limit. Retry tra {retry_after}s (attempt {attempt+1}/{max_retries})")
            time.sleep(retry_after)

        except APIStatusError as e:
            if e.status_code == 529:  # Overloaded
                delay = base_delay * (2 ** attempt)
                print(f"API overloaded. Retry tra {delay}s")
                time.sleep(delay)
            elif e.status_code >= 500:  # Server error — retry
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise  # 4xx errors non retriable (es. 400 bad request)

    raise RuntimeError(f"Max retries raggiunto dopo {max_retries} tentativi")
```

### Rate Limits (Sonnet 4.6, Tier 1)

| Limite | Valore |
|--------|--------|
| Requests per minute (RPM) | 50 |
| Input tokens per minute (ITPM) | 40.000 |
| Output tokens per minute (OTPM) | 8.000 |
| Requests per day (RPD) | 1.000 |

I limiti scalano con il tier (crescono con la spesa mensile). Tier 4+ ha limiti enterprise.

## Confronto Claude vs Competitor

| Aspetto | Claude 3.5 Sonnet | GPT-4o | Gemini 1.5 Pro |
|---------|------------------|--------|----------------|
| Context window | 200K | 128K | 1M (ma degrada) |
| Coding | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Reasoning | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Following istruzioni | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Onestà/calibrazione | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Multimodal | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Computer Use | ✅ (beta) | ✅ (Operator) | ❌ |
| Prezzo (Sonnet tier) | $3/$15 | $2.5/$10 | $3.5/$10.50 |
| Safety/Alignment | Molto alto (CAI) | Alto | Medio |

## Troubleshooting

### Scenario 1 — HTTP 529 "Overloaded" ricorrente

**Sintomo**: Le chiamate API falliscono con `APIStatusError: 529 Overloaded` in modo persistente, anche con retry.

**Causa**: Il cluster Anthropic è sotto carico elevato. Può accadere in fasce orarie di picco (07-10 UTC, 14-18 UTC) o quando si usano modelli premium come Opus ad alto volume.

**Soluzione**: Implementare exponential backoff con jitter, passare temporaneamente a Haiku, o spostare il workload sulla Batch API che è immune ai picchi sincroni.

```python
import random, time
from anthropic import APIStatusError

def call_with_backoff(client, **kwargs):
    for attempt in range(6):
        try:
            return client.messages.create(**kwargs)
        except APIStatusError as e:
            if e.status_code in (529, 503):
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
            else:
                raise
    raise RuntimeError("Max retries exceeded")
```

---

### Scenario 2 — `max_tokens` superato: risposta troncata

**Sintomo**: La risposta si interrompe nel mezzo di una frase o di un blocco di codice; `response.stop_reason == "max_tokens"`.

**Causa**: Il valore di `max_tokens` impostato è inferiore alla lunghezza effettiva della risposta generata. Non è un errore bloccante — l'API restituisce comunque HTTP 200.

**Soluzione**: Aumentare `max_tokens` oppure chiedere a Claude di essere più conciso nel system prompt. Per risposte strutturate (JSON, codice) sempre impostare un margine abbondante.

```python
# Verifica stop_reason prima di processare la risposta
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,   # aumentare se la risposta viene troncata
    messages=[...]
)

if response.stop_reason == "max_tokens":
    print("WARN: risposta troncata — aumentare max_tokens")

text = response.content[0].text
```

---

### Scenario 3 — Tool use in loop infinito (tool_use → tool_result → tool_use)

**Sintomo**: Claude risponde continuamente con `stop_reason == "tool_use"` senza mai produrre una risposta finale testuale; il ciclo si ripete indefinitamente.

**Causa**: La descrizione del tool non è abbastanza specifica, oppure il risultato restituito è ambiguo e Claude continua a cercare informazioni aggiuntive. Può anche essere dovuto a `tool_choice: {"type": "any"}` che forza sempre l'uso di un tool.

**Soluzione**: Impostare un limite massimo di turni, migliorare la descrizione dei tool, o aggiungere `tool_choice: {"type": "auto"}` per permettere a Claude di rispondere senza tool.

```python
MAX_TOOL_TURNS = 10
messages = [{"role": "user", "content": user_input}]

for turn in range(MAX_TOOL_TURNS):
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        tools=tools,
        tool_choice={"type": "auto"},  # non forzare uso tool
        messages=messages
    )
    if response.stop_reason == "end_turn":
        break
    # aggiungi risposta + risultati tool a messages
    messages.append({"role": "assistant", "content": response.content})
    tool_results = execute_tools(response.content)
    messages.append({"role": "user", "content": tool_results})
else:
    print("WARN: raggiunto limite massimo turni tool")
```

---

### Scenario 4 — Prompt caching: cache miss inatteso (costi più alti del previsto)

**Sintomo**: Nonostante `cache_control` sia configurato, i costi non scendono come atteso; i log mostrano sempre `cache_creation_input_tokens` senza `cache_read_input_tokens`.

**Causa**: Il contenuto marcato con `cache_control` cambia tra le chiamate (es. timestamp nel system prompt, variabili iniettate nel testo cachato), oppure è trascorso più di 5 minuti tra le chiamate (cache TTL scaduto).

**Soluzione**: Il testo cachato deve essere byte-identico tra le chiamate. Tenere fuori dalla sezione cachata qualsiasi parte dinamica. Monitorare `usage.cache_read_input_tokens` per verificare i cache hit.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            # SBAGLIATO: timestamp rende il testo sempre diverso
            # "text": f"Sei un esperto. Data: {datetime.now()}\n{handbook}",
            # CORRETTO: separare le parti statiche da quelle dinamiche
            "text": handbook_static_content,
            "cache_control": {"type": "ephemeral"}
        },
        {
            "type": "text",
            "text": f"Data corrente: {datetime.now().date()}"
            # parte dinamica fuori dal blocco cachato
        }
    ],
    messages=[{"role": "user", "content": domanda}]
)

# Verifica cache hit
usage = response.usage
print(f"Cache hit: {usage.cache_read_input_tokens} token")
print(f"Cache miss: {usage.cache_creation_input_tokens} token")
```

## Riferimenti

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Constitutional AI Paper](https://arxiv.org/abs/2212.08073)
- [Claude Model Overview](https://docs.anthropic.com/en/docs/about-claude/models/overview)
- [Tool Use Guide](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Prompt Caching Guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Computer Use Guide](https://docs.anthropic.com/en/docs/build-with-claude/computer-use)
