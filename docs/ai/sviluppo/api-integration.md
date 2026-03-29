---
title: "Integrazione API LLM — Anthropic, OpenAI e Pattern di Sviluppo"
slug: api-integration
category: ai
tags: [api, anthropic, openai, sdk, integration, streaming, error-handling, cost-optimization]
search_keywords: [anthropic api, openai api, llm api integration, python sdk anthropic, messages api, claude api python, openai python sdk, litellm, llm gateway, api key management, token counting, cost estimation, retry logic, exponential backoff, streaming llm, async llm, llm middleware, structured output, json mode, function calling integration]
parent: ai/sviluppo/_index
related: [ai/sviluppo/_index, ai/modelli/claude, ai/sviluppo/prompt-engineering, ai/agents/agent-patterns, ai/tokens-context/context-window]
official_docs: https://docs.anthropic.com/en/api/getting-started
status: complete
difficulty: intermediate
last_updated: 2026-03-27
---

# Integrazione API LLM — Anthropic, OpenAI e Pattern di Sviluppo

## Panoramica

Le API dei LLM seguono tutte un modello simile: una chiamata HTTP con un payload JSON che descrive il modello, il contesto (messages), e i parametri di generazione. Le differenze principali riguardano il formato dei messaggi, la gestione del system prompt, il tool use, e le feature avanzate (streaming, batch, caching). Conoscere i pattern corretti di integrazione — error handling, retry, cost management, structured output — è fondamentale per costruire applicazioni robuste.

## Anthropic SDK — Setup e Pattern Base

```bash
pip install anthropic
# oppure con tutte le dipendenze opzionali (async, vertex)
pip install "anthropic[all]"
```

```python
import anthropic
import os

# Configurazione base
client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],  # Mai hardcodare la chiave
    # timeout=30.0,               # default 10 minuti per richieste non-stream
    # max_retries=2,              # retry automatici su 429/529 (default 2)
)

# Chiamata base
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="Sei un esperto DevOps. Rispondi in modo conciso e tecnico.",
    messages=[
        {"role": "user", "content": "Qual è la differenza tra Deployment e StatefulSet in Kubernetes?"}
    ]
)

# Estrai il testo
text = response.content[0].text

# Metadata utili
print(f"Tokens usati — Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")
print(f"Stop reason: {response.stop_reason}")  # "end_turn", "max_tokens", "stop_sequence", "tool_use"
print(f"Model: {response.model}")
```

### Async Client

```python
import asyncio
import anthropic

async_client = anthropic.AsyncAnthropic()

async def process_many_requests(prompts: list[str]) -> list[str]:
    """Processa più richieste in parallelo (rispettando rate limits)."""
    import asyncio

    async def single_request(prompt: str) -> str:
        response = await async_client.messages.create(
            model="claude-haiku-4-5-20251001",  # più veloce per batch
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    # Limita la concorrenza per non superare rate limits
    semaphore = asyncio.Semaphore(5)  # max 5 richieste parallele

    async def throttled_request(prompt: str) -> str:
        async with semaphore:
            return await single_request(prompt)

    results = await asyncio.gather(*[throttled_request(p) for p in prompts])
    return list(results)

# Esecuzione
results = asyncio.run(process_many_requests(["domanda 1", "domanda 2", "domanda 3"]))
```

## Gestione della Conversazione Multi-Turn

```python
class ConversationManager:
    """Gestisce conversazioni multi-turn con Claude."""

    def __init__(self, model: str = "claude-sonnet-4-6", system: str = ""):
        self.client = anthropic.Anthropic()
        self.model = model
        self.system = system
        self.messages: list[dict] = []
        self.total_tokens = 0

    def chat(self, user_message: str, max_tokens: int = 2048) -> str:
        self.messages.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.system,
            messages=self.messages
        )

        assistant_message = response.content[0].text
        self.messages.append({"role": "assistant", "content": assistant_message})

        self.total_tokens += response.usage.input_tokens + response.usage.output_tokens

        return assistant_message

    def clear(self):
        """Reset conversation history."""
        self.messages = []

    def trim_to_last_n(self, n: int = 10):
        """Mantieni solo gli ultimi N messaggi per controllare il context."""
        # Mantieni sempre i messaggi in coppia (user + assistant)
        if len(self.messages) > n:
            self.messages = self.messages[-n:]

    def summarize_and_trim(self, keep_last: int = 4):
        """Riassumi la parte vecchia della conversazione per gestire context lungo."""
        if len(self.messages) <= keep_last:
            return

        to_summarize = self.messages[:-keep_last]
        recent = self.messages[-keep_last:]

        summary_response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"Riassumi questa conversazione in 3-5 frasi chiave:\n{str(to_summarize)}"
            }]
        )

        summary = summary_response.content[0].text
        self.messages = [
            {"role": "user", "content": f"[Riassunto conversazione precedente: {summary}]"},
            {"role": "assistant", "content": "Ho preso nota del contesto precedente."}
        ] + recent

# Uso
conv = ConversationManager(
    system="Sei un senior DevOps engineer che aiuta con problemi Kubernetes.",
)
print(conv.chat("Ho un pod in CrashLoopBackOff, come debuggo?"))
print(conv.chat("Il log mostra 'permission denied' su /var/lib/data"))
print(conv.chat("Come mai avviene questo con un volume PVC?"))
```

## Structured Output

Per estrarre dati strutturati, usare JSON mode o tool use come meccanismo forzato:

```python
import json
from pydantic import BaseModel, Field
from typing import Optional

# Pattern 1: JSON nel prompt (semplice ma meno affidabile)
def extract_json_simple(text: str, schema_description: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="Estrai sempre dati in formato JSON. Non includere testo fuori dal JSON.",
        messages=[{
            "role": "user",
            "content": f"""Estrai le seguenti informazioni in JSON:
Schema: {schema_description}

Testo: {text}

Rispondi SOLO con JSON valido, nessun altro testo."""
        }]
    )
    return json.loads(response.content[0].text)


# Pattern 2: Tool Use come "JSON mode" forzato (più affidabile)
def extract_structured(text: str, pydantic_model: type[BaseModel]) -> dict:
    """Usa tool use per forzare output strutturato."""
    schema = pydantic_model.model_json_schema()

    # Definisci un tool fittizio che rappresenta lo schema desiderato
    extraction_tool = {
        "name": "extract_data",
        "description": "Estrai i dati strutturati dal testo fornito",
        "input_schema": schema
    }

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=[extraction_tool],
        tool_choice={"type": "tool", "name": "extract_data"},  # forza uso del tool
        messages=[{
            "role": "user",
            "content": f"Estrai le informazioni da questo testo:\n\n{text}"
        }]
    )

    # L'output è garantito essere nell'input del tool_use block
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input


# Esempio con Pydantic
class Incident(BaseModel):
    title: str = Field(description="Titolo breve dell'incidente")
    severity: str = Field(description="Severità: P1, P2, P3, P4")
    affected_services: list[str] = Field(description="Servizi impattati")
    root_cause: Optional[str] = Field(description="Root cause se identificata")
    resolution: Optional[str] = Field(description="Come è stato risolto")
    duration_minutes: Optional[int] = Field(description="Durata in minuti")

incident_report = """
2024-03-15 14:32 UTC: Alle 14:32 abbiamo rilevato un incremento di errori 503
sul servizio api-gateway. I servizi payment e auth risultavano irraggiungibili.
L'incidente ha avuto una durata di circa 47 minuti. Root cause identificata:
una misconfiguration nel deployment del servizio auth (credenziali DB scadute).
Risolto con rollback alla versione precedente e update delle credenziali.
Classificazione: P2 - impatto su utenti finali.
"""

result = extract_structured(incident_report, Incident)
incident = Incident(**result)
print(f"Severità: {incident.severity}, Durata: {incident.duration_minutes} min")
```

## OpenAI SDK e Compatibilità

```python
from openai import OpenAI

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Chiamata base OpenAI
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Sei un assistente DevOps."},
        {"role": "user", "content": "Spiega il pattern Circuit Breaker."}
    ],
    max_tokens=1024,
    temperature=0.7
)

text = response.choices[0].message.content
usage = response.usage  # prompt_tokens, completion_tokens, total_tokens
```

## LiteLLM — Unified Gateway

**LiteLLM** fornisce un'interfaccia unificata per 100+ LLM (Claude, GPT, Gemini, Llama, ecc.) con la stessa API:

```python
from litellm import completion

# Claude via LiteLLM
response = completion(
    model="anthropic/claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Spiega Kubernetes in 3 frasi."}],
    max_tokens=512
)

# GPT-4o via LiteLLM (stessa interfaccia)
response = completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Spiega Kubernetes in 3 frasi."}],
    max_tokens=512
)

# Gemini via LiteLLM
response = completion(
    model="gemini/gemini-1.5-pro",
    messages=[{"role": "user", "content": "Spiega Kubernetes in 3 frasi."}],
    max_tokens=512
)

# Llama su Ollama (locale)
response = completion(
    model="ollama/llama3.1",
    messages=[{"role": "user", "content": "Spiega Kubernetes in 3 frasi."}],
    api_base="http://localhost:11434"
)

# Fallback automatico
response = completion(
    model="claude-sonnet-4-6",
    fallbacks=["gpt-4o", "gemini/gemini-1.5-pro"],  # se Claude fallisce, prova questi
    messages=[{"role": "user", "content": "Domanda"}]
)
```

### LiteLLM Proxy (Router)

Per ambienti enterprise con più team, LiteLLM Proxy centralizza routing, logging, rate limiting e cost tracking:

```yaml
# litellm_config.yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: llama-local
    litellm_params:
      model: ollama/llama3.1
      api_base: http://ollama:11434

router_settings:
  routing_strategy: "least-busy"  # o "latency-based", "cost-based"
  num_retries: 3

general_settings:
  master_key: sk-my-proxy-key
  database_url: postgresql://user:pass@postgres:5432/litellm

# Rate limiting per team
litellm_settings:
  default_team_settings:
    - team_id: "team-backend"
      max_parallel_requests: 10
      tpm_limit: 100000
    - team_id: "team-frontend"
      max_parallel_requests: 5
      tpm_limit: 50000
```

```bash
# Avvio proxy
litellm --config litellm_config.yaml --port 8000 --detailed_debug

# I client usano l'OpenAI SDK puntando al proxy
export OPENAI_API_BASE="http://litellm-proxy:8000"
export OPENAI_API_KEY="sk-my-proxy-key"
```

## Token Counting e Cost Estimation

```python
import anthropic

client = anthropic.Anthropic()

def estimate_cost(
    messages: list[dict],
    system: str = "",
    model: str = "claude-sonnet-4-6"
) -> dict:
    """Stima il costo prima di fare la chiamata."""

    # Conta i token con l'API ufficiale (non approssimata)
    token_count = client.messages.count_tokens(
        model=model,
        system=system,
        messages=messages
    )

    # Pricing (dollari per milione di token)
    pricing = {
        "claude-opus-4-6":        {"input": 15.00, "output": 75.00},
        "claude-sonnet-4-6":      {"input": 3.00,  "output": 15.00},
        "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
        # Cache write: +25% rispetto a input price
        # Cache read:  input_price * 0.10
    }

    p = pricing.get(model, {"input": 3.00, "output": 15.00})
    input_cost = (token_count.input_tokens / 1_000_000) * p["input"]

    return {
        "input_tokens": token_count.input_tokens,
        "estimated_input_cost_usd": input_cost,
        "model": model,
        "pricing": p
    }

# Monitoring costo in produzione
class CostTracker:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.calls = 0

    def track(self, response: anthropic.types.Message, model: str):
        pricing = {
            "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        }
        p = pricing.get(model, {"input": 3.00, "output": 15.00})

        input_cost  = (response.usage.input_tokens  / 1_000_000) * p["input"]
        output_cost = (response.usage.output_tokens / 1_000_000) * p["output"]

        self.total_input_tokens  += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        self.total_cost_usd      += input_cost + output_cost
        self.calls += 1

    def report(self):
        return {
            "total_calls": self.calls,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "avg_cost_per_call_usd": round(self.total_cost_usd / max(self.calls, 1), 4)
        }
```

## Error Handling Robusto

```python
import anthropic
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.cost_tracker = CostTracker()

    def complete(
        self,
        messages: list[dict],
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        system: str = "",
        max_retries: int = 5,
        **kwargs
    ) -> str:
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    **kwargs
                )

                self.cost_tracker.track(response, model)
                return response.content[0].text

            except anthropic.RateLimitError as e:
                # HTTP 429 — aspetta il tempo indicato dall'header retry-after
                retry_after = int(
                    getattr(e, "response", None) and
                    e.response.headers.get("retry-after", 60) or 60
                )
                logger.warning(f"Rate limit (attempt {attempt+1}). Waiting {retry_after}s...")
                time.sleep(retry_after)
                last_error = e

            except anthropic.APIStatusError as e:
                if e.status_code == 529:  # Overloaded
                    wait = min(2 ** attempt * 2, 60)
                    logger.warning(f"API overloaded (attempt {attempt+1}). Waiting {wait}s...")
                    time.sleep(wait)
                    last_error = e

                elif e.status_code in (500, 502, 503, 504):  # Server errors
                    wait = min(2 ** attempt, 30)
                    logger.warning(f"Server error {e.status_code} (attempt {attempt+1}). Waiting {wait}s...")
                    time.sleep(wait)
                    last_error = e

                elif e.status_code == 400:
                    # Bad request — non retriable (es. context troppo lungo)
                    logger.error(f"Bad request: {e.message}")
                    raise

                elif e.status_code == 401:
                    logger.error("Invalid API key")
                    raise

                else:
                    raise

            except anthropic.APIConnectionError as e:
                # Errore di rete — retry
                wait = min(2 ** attempt, 30)
                logger.warning(f"Connection error (attempt {attempt+1}). Waiting {wait}s...")
                time.sleep(wait)
                last_error = e

            except anthropic.APITimeoutError as e:
                # Timeout — retry con backoff
                wait = min(2 ** attempt * 5, 120)
                logger.warning(f"Timeout (attempt {attempt+1}). Waiting {wait}s...")
                time.sleep(wait)
                last_error = e

        raise RuntimeError(f"Max retries ({max_retries}) raggiunto. Ultimo errore: {last_error}")
```

## Configurazione per Ambienti Diversi

```python
# config/llm_settings.py
from dataclasses import dataclass
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class LLMConfig:
    model: str
    max_tokens: int
    temperature: float
    max_retries: int
    timeout_seconds: int
    enable_caching: bool
    log_requests: bool

CONFIGS = {
    Environment.DEVELOPMENT: LLMConfig(
        model="claude-haiku-4-5-20251001",  # modello economico per dev
        max_tokens=1024,
        temperature=0.7,
        max_retries=2,
        timeout_seconds=30,
        enable_caching=False,  # cache disabilitata in dev
        log_requests=True,     # log tutto in dev
    ),
    Environment.STAGING: LLMConfig(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0.5,
        max_retries=3,
        timeout_seconds=60,
        enable_caching=True,
        log_requests=True,
    ),
    Environment.PRODUCTION: LLMConfig(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0.3,
        max_retries=5,
        timeout_seconds=120,
        enable_caching=True,
        log_requests=False,  # solo errori in prod
    ),
}
```

## Sicurezza delle API Key

```python
# ✅ Corretti: variabili d'ambiente
import os
api_key = os.environ["ANTHROPIC_API_KEY"]

# ✅ Corretti: secret manager (AWS, Azure, GCP)
import boto3
def get_api_key_from_aws() -> str:
    client = boto3.client("secretsmanager", region_name="eu-west-1")
    response = client.get_secret_value(SecretId="anthropic-api-key")
    return response["SecretString"]

# ✅ Corretti: Kubernetes secret
# kubectl create secret generic anthropic-key --from-literal=key=sk-ant-...
# Montare come env var nel Pod spec

# ❌ Sbagliato: hardcoded
api_key = "sk-ant-api03-..."  # mai fare questo

# ❌ Sbagliato: in file di configurazione versionati
# config.yaml: api_key: "sk-ant-api03-..."  # gitignore non è sufficiente

# ✅ Rotazione automatica key (pattern con cache)
import time
_cached_key = None
_key_expiry = 0

def get_rotating_api_key() -> str:
    global _cached_key, _key_expiry
    if time.time() > _key_expiry:
        _cached_key = get_api_key_from_aws()
        _key_expiry = time.time() + 3600  # refresh ogni ora
    return _cached_key
```

## Troubleshooting

### Scenario 1 — Rate Limit 429 / Overloaded 529

**Sintomo:** Le chiamate API falliscono con `RateLimitError` (429) o `APIStatusError` con status 529 in modo intermittente.

**Causa:** Superamento del limite di richieste al minuto (RPM) o di token al minuto (TPM) assegnato al tier corrente; oppure carico elevato sui server Anthropic (529).

**Soluzione:** Implementare exponential backoff rispettando l'header `retry-after`. Per 529 usare backoff con jitter. Ridurre la concorrenza con `asyncio.Semaphore`.

```python
import time, random

def backoff_wait(attempt: int, base: float = 2.0, max_wait: float = 60.0) -> float:
    jitter = random.uniform(0, 1)
    wait = min(base ** attempt + jitter, max_wait)
    time.sleep(wait)
    return wait

# Verifica il tuo tier e i limiti attuali
# https://console.anthropic.com/settings/limits
```

---

### Scenario 2 — `max_tokens` raggiunto (stop_reason: "max_tokens")

**Sintomo:** La risposta viene troncata e `response.stop_reason == "max_tokens"`. Il testo finisce a metà frase.

**Causa:** Il valore di `max_tokens` impostato è insufficiente per il task corrente. Non ha nulla a che fare con il context window.

**Soluzione:** Aumentare `max_tokens` oppure suddividere il task in sotto-richieste più piccole. Monitorare `stop_reason` sistematicamente.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,  # aumenta il limite di output
    messages=[...]
)

if response.stop_reason == "max_tokens":
    # La risposta è troncata — gestisci il caso
    print("WARNING: risposta troncata, considera di aumentare max_tokens o spezzare il prompt")
```

---

### Scenario 3 — `InvalidRequestError` 400 — Context troppo lungo

**Sintomo:** `APIStatusError` con status 400 e messaggio `"prompt is too long"` o `"context_length_exceeded"`.

**Causa:** Il totale di token (system + messages history + strumenti) supera il context window del modello (200K token per Claude 3+).

**Soluzione:** Usare `count_tokens` per monitorare prima della chiamata. Applicare trimming/summarization della history.

```python
# Verifica preventiva del context
token_count = client.messages.count_tokens(
    model="claude-sonnet-4-6",
    system=system_prompt,
    messages=messages
)

MAX_INPUT_TOKENS = 180_000  # margine di sicurezza

if token_count.input_tokens > MAX_INPUT_TOKENS:
    # Applica trimming prima di chiamare
    conv_manager.trim_to_last_n(10)
    # oppure
    conv_manager.summarize_and_trim(keep_last=4)
```

---

### Scenario 4 — Tool Use: il modello non chiama il tool atteso

**Sintomo:** Con `tool_choice={"type": "auto"}` il modello risponde in testo invece di invocare il tool. L'output non è nel formato strutturato atteso.

**Causa:** Il modello ha deciso autonomamente che il testo era una risposta migliore, oppure la descrizione del tool è ambigua.

**Soluzione:** Usare `tool_choice={"type": "tool", "name": "nome_tool"}` per forzare l'invocazione. Migliorare la `description` del tool con istruzioni esplicite su quando usarlo.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=[extraction_tool],
    tool_choice={"type": "tool", "name": "extract_data"},  # forza il tool
    messages=[{"role": "user", "content": testo}]
)

# Verifica che il blocco tool_use sia presente
tool_blocks = [b for b in response.content if b.type == "tool_use"]
if not tool_blocks:
    raise ValueError(f"Tool non invocato. Stop reason: {response.stop_reason}. Content: {response.content}")
```

---

## Riferimenti

- [Anthropic API Reference](https://docs.anthropic.com/en/api/)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
