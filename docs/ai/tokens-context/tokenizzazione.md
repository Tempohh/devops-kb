---
title: "Tokenizzazione — BPE, Vocab e Costo Token"
slug: tokenizzazione
category: ai
tags: [tokenization, bpe, tiktoken, tokens, vocab]
search_keywords: [tokenizzazione LLM, Byte Pair Encoding, BPE, tiktoken, vocab size, subword tokenization, cl100k_base, Llama tokenizer, SentencePiece, costo token, token counting, lingua e token, codice e token, caratteri speciali token]
parent: ai/tokens-context/_index
related: [ai/tokens-context/context-window, ai/sviluppo/prompt-engineering, ai/modelli/_index]
official_docs: https://github.com/openai/tiktoken
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Tokenizzazione — BPE, Vocab e Costo Token

## Panoramica

La tokenizzazione è il processo che trasforma il testo grezzo in sequenze di numeri interi (token ID) che il modello può elaborare. Gli LLM non vedono caratteri o parole: vedono sequenze di ID numerici, ognuno dei quali corrisponde a un'unità di testo nel vocabolario del modello. Il modo in cui il testo viene spezzato in token ha implicazioni dirette su costo (si pagano i token), sulla qualità dell'output (lingue diverse sono trattate diversamente), e su certi comportamenti del modello (numeri, URL, codice).

Tutti i principali LLM usano la tokenizzazione **subword**: le unità di base non sono interi caratteri (troppo inefficiente) né intere parole (vocabolario troppo grande, OOV problem), ma frammenti di parola statisticamente comuni nel corpus di training.

## 1. Byte Pair Encoding (BPE)

BPE è l'algoritmo più usato per costruire il vocabolario di un tokenizer LLM. Fu originariamente un algoritmo di compressione dati (1994) adattato per il NLP da Sennrich et al. (2016).

### Algoritmo BPE — Come Funziona

**Input**: corpus di testo, dimensione vocabolario target V.

**Fase 1 — Inizializzazione**: il vocabolario parte dai singoli byte (256 simboli per UTF-8) o dai singoli caratteri. Ogni parola viene rappresentata come sequenza di caratteri + simbolo di fine parola.

```
"low": l o w </w>
"lower": l o w e r </w>
"newest": n e w e s t </w>
"widest": w i d e s t </w>
```

**Fase 2 — Merge iterativi**: si conta ogni coppia adiacente di simboli nel corpus, si prende la più frequente, la si fonde in un nuovo simbolo. Si ripete fino a raggiungere V.

```
Iterazione 1: coppia più frequente = (e, s) → "es"
  "newest": n e w es t </w>
  "widest": w i d es t </w>

Iterazione 2: coppia più frequente = (es, t) → "est"
  "newest": n e w est </w>
  "widest": w i d est </w>

... dopo V iterazioni, il vocabolario contiene sequenze comuni
```

**Risultato**: un vocabolario di V simboli (tipicamente 32K-130K) che bilancia efficienza e copertura.

### BPE con Byte Fallback

I tokenizer moderni (GPT-4, Claude) usano **Byte-level BPE**: invece di caratteri, il vocabolario base è l'insieme dei 256 byte. Questo garantisce che qualsiasi testo (incluso binario, emoji, lingue rare) possa essere tokenizzato senza OOV (Out Of Vocabulary), al costo di più token per caratteri non latini.

### Algoritmo di Tokenizzazione (Inference)

Dato un testo nuovo, la tokenizzazione applica gli stessi merge nell'ordine imparato durante il training:

```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer

text = "Hello, world! Questo è un esempio di tokenizzazione."
tokens = enc.encode(text)
print(f"Token IDs: {tokens}")
# [9906, 11, 1917, 0, 1115, 48244, 382, 653, 40783, 13]

print(f"Numero token: {len(tokens)}")

# Decodifica
decoded = enc.decode(tokens)
print(f"Testo decodificato: {decoded}")

# Visualizzazione per token
for token_id in tokens:
    token_text = enc.decode([token_id])
    print(f"ID {token_id:6d} → '{token_text}'")
```

## 2. Vocabolari dei Principali Modelli

| Modello | Tokenizer | Vocab Size | Libreria |
|---------|-----------|-----------|---------|
| GPT-4, GPT-3.5 | cl100k_base | 100.277 | tiktoken |
| Claude (Anthropic) | Proprietario (simile cl100k) | ~100K | anthropic SDK |
| Llama 3.x | Llama 3 Tokenizer | 128.256 | sentencepiece / transformers |
| Llama 2 | Llama 2 Tokenizer | 32.000 | sentencepiece |
| Mistral 7B | Mistral Tokenizer | 32.000 | sentencepiece |
| Gemma 2 | Gemma Tokenizer | 256.000 | sentencepiece |
| Qwen 2.5 | Qwen Tokenizer (tiktoken-based) | 151.936 | tiktoken |
| GPT-2 (storico) | gpt2 | 50.257 | tiktoken |

!!! note "Perché vocab size più grande è meglio"
    Un vocabolario più grande significa che sequenze comuni vengono compresse in meno token. Llama 3 con 128K vocab tokenizza il codice e le lingue non-latine in ~20% meno token rispetto a Llama 2 con 32K vocab. Meno token = meno costo, più contesto disponibile, inferenza più veloce.

## 3. Differenze per Lingua e Tipo di Contenuto

### Efficienza per Lingua

L'inglese è il punto di riferimento. Le altre lingue usano mediamente più token per esprimere lo stesso concetto.

| Lingua | Token per concetto (relativo a EN) | Motivo |
|--------|------------------------------------|--------|
| Inglese (EN) | 1× (baseline) | Training data dominante |
| Francese, Spagnolo | 1.1-1.2× | Morphologia simile, buona copertura |
| Italiano | 1.1-1.3× | Suffissi vari, vocabolario ricco |
| Tedesco | 1.2-1.4× | Parole composte molto lunghe |
| Arabo | 1.5-2× | Script RTL, morfologia complessa |
| Cinese (CJK) | 1.5-2× (per carattere) | 1 carattere ≈ 1-3 token |
| Russo (Cirillico) | 1.5-2.5× | Alfabeto diverso |
| Emoji | 1-3 token per emoji | Dipende dall'emoji |

```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

sentences = {
    "English": "The deployment pipeline failed because the Docker image build exceeded the timeout.",
    "Italian": "La pipeline di deployment ha fallito perché la build dell'immagine Docker ha superato il timeout.",
    "Chinese": "部署管道失败，因为Docker镜像构建超过了超时限制。",
    "Arabic":  "فشل خط أنابيب النشر لأن بناء صورة Docker تجاوز الحد الزمني.",
}

for lang, text in sentences.items():
    tokens = enc.encode(text)
    words = len(text.split())
    print(f"{lang:10}: {len(tokens):3d} token | {words:4d} parole | ratio {len(tokens)/words:.2f}")

# Output approssimativo:
# English   :  15 token |   14 parole | ratio 1.07
# Italian   :  22 token |   16 parole | ratio 1.38
# Chinese   :  20 token |   30 char   | ratio 0.67  (chars ≠ words)
# Arabic    :  25 token |    8 parole | ratio 3.12
```

### Codice Sorgente

Il codice ha un rapporto token/carattere diverso dal testo naturale a causa di spazi, indentazione, caratteri speciali.

```python
code_snippets = {
    "Python function": """def calculate_checksum(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()""",

    "YAML K8s": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: production""",

    "Bash command": "kubectl get pods -n production --field-selector=status.phase=Running -o json | jq '.items[].metadata.name'",
}

for name, code in code_snippets.items():
    tokens = enc.encode(code)
    print(f"{name}: {len(tokens)} token, {len(code)} chars, ratio {len(tokens)/len(code):.2f} tok/char")
```

### Casi Edge Importanti

```python
# Numeri: ogni cifra è spesso un token separato
enc.encode("1234567890")  # → potenzialmente 10 token separati

# URL: molto costosi in token
enc.encode("https://registry.terraform.io/providers/hashicorp/aws/latest/docs")
# → ~20-25 token

# Spazi e newline: dipendono dal tokenizer
enc.encode("    ")  # 4 spazi → 1-2 token (dipende)
enc.encode("\n\n\n") # 3 newline → 1-3 token

# Parole maiuscole/minuscole → token diversi
enc.encode("Kubernetes")  # diverso da enc.encode("kubernetes")

# Punteggiatura incollata alla parola → token diversi
enc.encode("API.")   # diverso da enc.encode("API") + enc.encode(".")
enc.encode("API,")   # ancora diverso
```

## 4. Conteggio Token in Pratica

### Con tiktoken (OpenAI)

```python
import tiktoken

def count_tokens_openai(text: str, model: str = "gpt-4o") -> int:
    """Conta i token per un modello OpenAI."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def count_chat_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    """Conta i token totali in una lista di messaggi chat."""
    encoding = tiktoken.encoding_for_model(model)
    # Overhead per struttura messaggio
    tokens_per_message = 3  # <im_start>{role}\n{content}<im_end>\n
    tokens_per_name = 1

    total = 3  # <im_start>assistant overhead
    for msg in messages:
        total += tokens_per_message
        for key, value in msg.items():
            total += len(encoding.encode(value))
            if key == "name":
                total += tokens_per_name
    return total

# Esempio
messages = [
    {"role": "system", "content": "Sei un esperto DevOps."},
    {"role": "user", "content": "Come configuro un Horizontal Pod Autoscaler?"}
]
print(f"Token stimati: {count_chat_tokens(messages)}")
```

### Con Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic()

# Conta token prima dell'invio (senza consumare l'API per la risposta)
response = client.messages.count_tokens(
    model="claude-3-5-sonnet-20241022",
    system="Sei un esperto DevOps senior.",
    messages=[
        {"role": "user", "content": "Analizza questo Dockerfile:\n```\nFROM ubuntu:22.04\n...\n```"}
    ]
)
print(f"Input token: {response.input_tokens}")
```

### Con HuggingFace transformers

```python
from transformers import AutoTokenizer

# Llama 3
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct")
text = "Come si configura un Ingress in Kubernetes?"
tokens = tokenizer.encode(text)
print(f"Llama 3.1 tokenizer: {len(tokens)} token")

# Confronto tra tokenizer
tokenizers = {
    "GPT-4 (cl100k)": tiktoken.get_encoding("cl100k_base"),
}
llama_tok = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3.1-8B")

for name, tok in tokenizers.items():
    print(f"{name}: {len(tok.encode(text))} token")
print(f"Llama 3: {len(llama_tok.encode(text))} token")
```

## 5. Calcolo del Costo

Il costo delle API LLM è calcolato per token (separatamente per input e output).

```python
def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_million: float,
    output_price_per_million: float
) -> float:
    """Calcola il costo in USD per una singola chiamata API."""
    input_cost = (input_tokens / 1_000_000) * input_price_per_million
    output_cost = (output_tokens / 1_000_000) * output_price_per_million
    return input_cost + output_cost

# Prezzi di esempio (Feb 2026) — verificare i prezzi aggiornati!
PRICING = {
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku":  {"input": 0.80, "output": 4.00},
    "gpt-4o":            {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":       {"input": 0.15, "output": 0.60},
}

# Stima costo mensile per un'applicazione
def estimate_monthly_cost(
    daily_requests: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    model: str
) -> dict:
    pricing = PRICING[model]
    daily_cost = calculate_cost(
        daily_requests * avg_input_tokens,
        daily_requests * avg_output_tokens,
        pricing["input"],
        pricing["output"]
    )
    return {
        "daily_usd": round(daily_cost, 4),
        "monthly_usd": round(daily_cost * 30, 2),
        "daily_input_tokens": daily_requests * avg_input_tokens,
        "daily_output_tokens": daily_requests * avg_output_tokens
    }

# Esempio: chatbot con 1000 richieste/giorno, prompt 500 token, risposta 300 token
print(estimate_monthly_cost(1000, 500, 300, "claude-3-5-sonnet"))
# {'daily_usd': 6.0, 'monthly_usd': 180.0, ...}

print(estimate_monthly_cost(1000, 500, 300, "claude-3-5-haiku"))
# {'daily_usd': 1.6, 'monthly_usd': 48.0, ...}
```

## 6. Token Budget Planning

### Distribuzione Consigliata del Context

Per applicazioni con context window di 200K (Claude):

```
Context Window (200K token)
├── System prompt:              500 - 2.000 token  (0.25-1%)
├── Pochi-shot examples:          0 - 5.000 token  (0-2.5%)
├── Retrieved context (RAG):  5.000 - 50.000 token (2.5-25%)
├── Conversation history:     5.000 - 20.000 token (2.5-10%)
├── User message:             1.000 - 10.000 token (0.5-5%)
└── Reserved for output:      4.096 - 16.384 token (2-8%)
```

### Strategie per Ridurre i Token

```python
# 1. Compressione del contesto
def compress_log(log_lines: list[str], max_lines: int = 50) -> str:
    """Tieni solo le ultime N righe e aggiungi ellipsis."""
    if len(log_lines) <= max_lines:
        return "\n".join(log_lines)
    return f"[... {len(log_lines) - max_lines} righe omesse ...]\n" + "\n".join(log_lines[-max_lines:])

# 2. Rimozione di ridondanze
import re

def clean_k8s_manifest(yaml_text: str) -> str:
    """Rimuove campi non essenziali da manifest Kubernetes."""
    # Rimuove righe con valori null o vuoti
    lines = yaml_text.split('\n')
    cleaned = [l for l in lines if not re.match(r'\s*\w+:\s*(null|""|{}|\[\])$', l)]
    return '\n'.join(cleaned)

# 3. Abbreviazioni sistematiche nel system prompt
compact_system = """
Abbreviazioni: K8s=Kubernetes, tf=Terraform, dp=deployment, svc=service.
Formato risposta: JSON con campi: issue, severity, fix.
"""

# 4. Structured output per ridurre verbosità risposta
output_instruction = """
Rispondi SOLO con JSON valido, nessun testo aggiuntivo:
{"severity": "critical|high|medium|low", "issue": "...", "fix": "..."}
"""
```

## 7. Differenze tra Tokenizer

Lo stesso testo produce token diversi con tokenizer diversi:

```python
# "Hello, DevOps world! 2024"
# GPT-4 (cl100k): [9906, 11, 15707, 20275, 1917, 0, 220, 2366, 19]  → 9 token
# Llama 3 (128K vocab): diversi ID, possibile numero diverso di token
# Mistral (32K vocab): molti più merge richiesti → token più lunghi

# Implicazione pratica:
# Il costo di una chiamata GPT vs Claude può differire
# anche con lo stesso testo, se i tokenizer sono diversi.
# Usare sempre il tokenizer ufficiale del modello per stime accurate.
```

!!! warning "Tokenizer Anthropic non è pubblico"
    Anthropic non pubblica il tokenizer di Claude come libreria standalone. Per contare i token con Claude, usa l'API `count_tokens` (gratuita) o stima con cl100k_base di tiktoken (errore tipico <5%).

## Best Practices

- **Sempre misurare**: non stimare "occhio" i token. Usa tiktoken o l'API count_tokens prima di mandare in produzione.
- **Monitora il token usage in produzione**: traccia `input_tokens` e `output_tokens` in ogni risposta API per rilevare anomalie e calcolare i costi effettivi.
- **Preferisci output strutturati brevi**: istruire il modello a rispondere in JSON compatto invece di prosa verbose riduce i token di output (che costano di più).
- **Cache il system prompt**: con prompt caching (Claude) un system prompt di 2000 token ripetuto 10.000 volte costa 90% in meno. Vedi [Context Window](context-window.md).
- **Lingua del prompt**: i prompt in inglese usano meno token. Se il modello lo supporta bene, considera di mantenere il system prompt in inglese e l'output in italiano.

## Troubleshooting

### Scenario 1 — Il conteggio token dell'SDK differisce da tiktoken

**Sintomo:** `count_tokens` di Anthropic restituisce un numero diverso da quello calcolato con `tiktoken.get_encoding("cl100k_base")`.

**Causa:** Anthropic usa un tokenizer proprietario non identico a cl100k_base. Le differenze sono tipicamente <5% ma possono salire per testo non-ASCII, codice o caratteri speciali.

**Soluzione:** Per Claude, usare sempre l'API `count_tokens` come fonte di verità. Tiktoken è solo una stima rapida per GPT-4.

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.count_tokens(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": testo}]
)
print(f"Token reali per Claude: {response.input_tokens}")
```

---

### Scenario 2 — I token consumati sono molti più del previsto in produzione

**Sintomo:** Il costo API mensile supera di molto le stime iniziali. I log mostrano `input_tokens` elevati anche per richieste semplici.

**Causa:** Il system prompt, la conversation history accumulata, o i retrieved chunk RAG vengono inviati per intero ad ogni chiamata senza troncamento. Il contatore token non viene monitorato in modo continuo.

**Soluzione:** Aggiungere logging del token usage su ogni risposta e impostare alert sui costi. Applicare strategie di compressione del contesto.

```python
import anthropic

client = anthropic.Anthropic()

def call_with_token_logging(messages: list, system: str = "") -> str:
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system,
        messages=messages
    )
    usage = response.usage
    print(f"[TOKEN LOG] input={usage.input_tokens} output={usage.output_tokens} "
          f"total={usage.input_tokens + usage.output_tokens}")
    return response.content[0].text
```

---

### Scenario 3 — Testo in italiano usa molti più token del previsto

**Sintomo:** Prompt identici in italiano costano il 30-50% in più rispetto alla versione inglese. Il modello a volte tronca la risposta prima di finire.

**Causa:** I tokenizer LLM sono addestrati prevalentemente su testo inglese. L'italiano, con i suoi suffissi variabili e accenti, viene segmentato in più subword rispetto all'inglese.

**Soluzione:** Mantenere il system prompt in inglese dove possibile. Per contenuti obbligatoriamente in italiano, aumentare il budget di token del 30-40% rispetto alle stime in inglese.

```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

prompt_en = "Analyze the Kubernetes deployment configuration and identify potential issues."
prompt_it = "Analizza la configurazione del deployment Kubernetes e identifica i problemi potenziali."

tok_en = len(enc.encode(prompt_en))
tok_it = len(enc.encode(prompt_it))

print(f"English: {tok_en} token")
print(f"Italian: {tok_it} token")
print(f"Overhead italiano: +{((tok_it/tok_en)-1)*100:.1f}%")
```

---

### Scenario 4 — `tiktoken.encoding_for_model()` lancia `KeyError` per un modello recente

**Sintomo:** `tiktoken.encoding_for_model("gpt-4o-2024-11-20")` (o altro modello recente) lancia `KeyError: 'gpt-4o-2024-11-20'`.

**Causa:** La versione installata di tiktoken non include il mapping per il modello più recente. Il package model→encoding è aggiornato con nuove release.

**Soluzione:** Aggiornare tiktoken, oppure usare il fallback su cl100k_base (valido per tutti i modelli GPT-4 family).

```bash
# Aggiorna tiktoken all'ultima versione
pip install --upgrade tiktoken

# Verifica modelli supportati
python -c "import tiktoken; print(list(tiktoken.model.MODEL_TO_ENCODING.keys()))"
```

```python
import tiktoken

def safe_encode(text: str, model: str = "gpt-4o") -> list[int]:
    """Tokenizza con fallback automatico se il modello non è mappato."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return enc.encode(text)
```

## Riferimenti

- [tiktoken GitHub](https://github.com/openai/tiktoken) — Tokenizer GPT-4, installazione e utilizzo
- [OpenAI Tokenizer Visualizer](https://platform.openai.com/tokenizer) — Tool interattivo
- [Anthropic Token Counting API](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — Come contare token con Claude
- [Neural Machine Translation of Rare Words with Subword Units (Sennrich et al., 2016)](https://arxiv.org/abs/1508.07909) — Paper originale BPE per NLP
- [Language Models are Few-Shot Learners (Brown et al., 2020)](https://arxiv.org/abs/2005.14165) — GPT-3, dove tiktoken è stato standardizzato
