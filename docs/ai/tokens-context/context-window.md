---
title: "Context Window e KV Cache"
slug: context-window
category: ai
tags: [context-window, kv-cache, long-context, position-encoding, rope]
search_keywords: [context window LLM, finestra di contesto, KV cache, key value cache, long context, contesto lungo, RoPE, YaRN, sliding window attention, needle in haystack, lost in the middle, prompt caching, context compression, position encoding, primacy recency bias]
parent: ai/tokens-context/_index
related: [ai/tokens-context/tokenizzazione, ai/sviluppo/rag, ai/sviluppo/prompt-engineering, ai/mlops/infrastruttura-gpu]
official_docs: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# Context Window e KV Cache

## Panoramica

La context window è il confine fondamentale di ciò che un LLM può "vedere" durante una singola inferenza. Tutto ciò che è dentro la finestra contribuisce alla risposta; tutto ciò che è fuori è completamente invisibile. Comprendere come questa finestra funziona internamente — attraverso il meccanismo KV Cache e gli encodings posizionali — è essenziale per progettare applicazioni AI che si comportino in modo prevedibile con input lunghi.

Non basta sapere che un modello supporta 200K token: ci sono effetti di "memoria" non uniforme all'interno della finestra stessa, costi infrastrutturali proporzionali alla lunghezza del contesto, e strategie architetturali per gestire documenti che superano qualsiasi finestra. Questo documento copre tutti questi aspetti a livello tecnico.

## 1. Cos'è la Context Window

La context window definisce il numero massimo di token che il modello può processare in una singola forward pass. Include l'intero input (system prompt, messaggi precedenti, nuovo messaggio) più lo spazio per l'output.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTEXT WINDOW (200K)                        │
│                                                                  │
│  ┌────────────┐  ┌─────────────────┐  ┌──────────┐  ┌────────┐ │
│  │   System   │  │   Conversation  │  │  User    │  │Output  │ │
│  │   Prompt   │  │    History      │  │  Msg     │  │(max)   │ │
│  │  ~500 tok  │  │  ~10.000 tok    │  │ ~2K tok  │  │ 8K tok │ │
│  └────────────┘  └─────────────────┘  └──────────┘  └────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Quando l'input supera la context window, il comportamento tipico è il **troncamento**: i token oltre il limite vengono scartati (solitamente dall'inizio o dalla fine, dipende dall'implementazione). Il modello non genera errori — produce semplicemente una risposta basata su un contesto incompleto, spesso senza che l'applicazione se ne accorga.

## 2. KV Cache — Meccanismo Interno

### Come Funziona l'Attention

Nel Transformer, ogni layer di attention calcola tre matrici per ogni token nel contesto:
- **Q** (Query): "cosa sto cercando?"
- **K** (Key): "cosa posso offrire?"
- **V** (Value): "qual è il mio contenuto?"

L'attention score è: `Attention(Q, K, V) = softmax(QK^T / √d_k) · V`

Durante la **generazione** (decoding), il modello genera un token alla volta. Ad ogni step, il token appena generato deve attendere a TUTTI i token precedenti. Questo richiede ricalcolare K e V per tutti i token precedenti — operazione computazionalmente costosa.

### Come Funziona il KV Cache

Il KV Cache salva le matrici K e V calcolate per tutti i token del contesto. Ad ogni step di generazione si calcola solo K e V del nuovo token, non dell'intera sequenza.

```
Senza KV Cache (inefficiente):
Step 1: calcola Q,K,V per [tok1]
Step 2: calcola Q,K,V per [tok1, tok2]
Step 3: calcola Q,K,V per [tok1, tok2, tok3]
...
Step N: calcola Q,K,V per [tok1 ... tokN] — O(N²) complessità totale

Con KV Cache:
Step 1: calcola Q,K,V per [tok1] → salva K1,V1 in cache
Step 2: calcola solo Q,K,V per [tok2] → aggiunge K2,V2 in cache. Riusa K1,V1
Step 3: calcola solo Q,K,V per [tok3] → aggiunge K3,V3 in cache. Riusa K1,K2,V1,V2
...
Step N: calcola solo Q,K,V per [tokN] → O(N) complessità per step
```

### Dimensione del KV Cache

```
KV Cache size = 2               # K e V
              × num_layers      # per ogni layer Transformer
              × num_kv_heads    # numero di KV heads (GQA)
              × head_dim        # dimensione di ogni head
              × sequence_length # lunghezza del contesto
              × dtype_bytes     # 2 per FP16, 2 per BF16

Esempi:

Llama 3.1 8B (FP16, GQA con 8 KV heads):
= 2 × 32 × 8 × 128 × seq_len × 2
= 131.072 bytes per token
= 128 KB per token

Per 8K token di context:   1 GB KV cache
Per 32K token di context:  4 GB KV cache
Per 128K token di context: 16 GB KV cache (!) — più dei pesi del modello (~16GB FP16)

Llama 3.1 70B (FP16, GQA con 8 KV heads):
= 2 × 80 × 8 × 128 × seq_len × 2
= 327.680 bytes per token

Per 128K token di context: 40 GB KV cache — questo spiega perché serve molto VRAM
```

!!! warning "VRAM per context lunghi"
    Con context window di 128K o 200K, il KV cache può facilmente superare la dimensione dei pesi del modello. Un Llama 3.1 70B con context 128K richiede ~140GB per i pesi + ~40GB per il KV cache = ~180GB totali. Richiede 3× H100 80GB.

### GQA — Grouped Query Attention

Per ridurre la dimensione del KV cache, i modelli moderni usano Grouped Query Attention (GQA): invece di avere una coppia K,V per ogni attention head, si raggruppano più query heads a condividere le stesse K,V.

```
Multi-Head Attention (MHA): Q₁K₁V₁, Q₂K₂V₂, ..., QₙKₙVₙ
Multi-Query Attention (MQA): Q₁Q₂...Qₙ condividono K₁V₁
Grouped Query Attention (GQA): Q₁Q₂ → K₁V₁, Q₃Q₄ → K₂V₂, ...

Llama 3.1 8B: 32 query heads, 8 KV heads (ratio 4:1) → KV cache 4× più piccolo
```

## 3. Position Encodings e Context Lungo

### Come i Transformer "Sanno" l'Ordine dei Token

A differenza delle RNN, i Transformer processano tutti i token in parallelo — senza meccanismi espliciti, perderebbero l'informazione sull'ordine. I **positional encodings** (PE) aggiungono informazione sulla posizione di ogni token.

### RoPE — Rotary Position Embedding

I modelli moderni (Llama 3, Mistral, Claude) usano RoPE: invece di aggiungere un vettore di posizione all'embedding, si ruota le matrici Q e K di un angolo proporzionale alla posizione.

```
Proprietà chiave di RoPE:
- L'attention score tra due token dipende dalla loro posizione RELATIVA, non assoluta
- Questo rende RoPE naturalmente estendibile a sequenze più lunghe
- Il modello può generalizzare a posizioni non viste nel training

Formula semplificata:
Q_rotated[pos] = Q[pos] × R(pos)
K_rotated[pos] = K[pos] × R(pos)
Q·K = (Q × R(m)) · (K × R(n)) = f(m-n)  — dipende solo da m-n
```

### YaRN — Context Extension

I modelli vengono addestrati su sequenze fino a una certa lunghezza. Per usarli su sequenze più lunghe, esistono tecniche di estensione:

- **YaRN (Yet another RoPE extension method)**: modifica le frequenze di RoPE per adattarsi a contesti più lunghi senza perdita di qualità. Llama 3.1 128K usa YaRN.
- **LongRoPE**: estensione progressiva della context window durante fine-tuning
- **ALiBi (Attention with Linear Biases)**: penalizza linearmente l'attention score in base alla distanza — naturalmente extendibile

## 4. Primacy e Recency Bias

La ricerca empirica ha mostrato che gli LLM non accedono all'informazione uniformemente nel contesto. Tendono a ricordare meglio le informazioni all'**inizio** (primacy) e alla **fine** (recency) del contesto, mentre le informazioni nel **mezzo** vengono spesso ignorate o "dimenticate".

### "Lost in the Middle" (Liu et al., 2023)

Uno studio influente ("Lost in the Middle: How Language Models Use Long Contexts") ha dimostrato che le performance degli LLM degradano significativamente quando l'informazione critica è posizionata nel centro del contesto, anche se teoricamente il modello può vedere tutta la finestra.

```
Contesto = [doc1, doc2, doc3, ..., doc20]
Risposta corretta si trova in doc10 (al centro)

Performance LLM:
├── Se info è in doc1 o doc2 (inizio): ~90% accuracy
├── Se info è in doc18, doc19 (fine):  ~85% accuracy
└── Se info è in doc8-12 (centro):     ~50-60% accuracy (!)
```

### Implicazioni Pratiche

```
Struttura consigliata del prompt per task critici:

[SYSTEM PROMPT]
[INFORMAZIONE CRITICA — metti qui]   ← primacy
[Documenti di contesto / RAG chunks]
[Conversation history]
[USER MESSAGE — contiene la domanda] ← recency

NON fare:
[SYSTEM PROMPT]
[Docum. di contesto molto lunghi]
[INFORMAZIONE CRITICA — nel mezzo!]  ← persa!
[USER MESSAGE]
```

!!! tip "Needle in a Haystack test"
    Il "Needle in a Haystack" è un test standard: si nasconde un'informazione specifica ("needle") in vari punti di un contesto lungo ("haystack") e si verifica se il modello la trova. Usalo per valutare empiricamente il comportamento del modello specifico con il tuo tipo di contesto.

## 5. Strategie per Context Lunghi

### 5.1 Chunking e Sliding Window

Suddividi il documento in chunk sovrapposti e processa ogni chunk separatamente.

```python
def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Divide il testo in chunk con overlap per non perdere contesto ai bordi."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap  # avanza con overlap
    return chunks
```

**Limite**: perde il contesto globale. Informazioni che attraversano più chunk possono essere perse.

### 5.2 RAG — Retrieval Instead of Full Context

Invece di inserire tutto il documento nel contesto, si recupera solo i chunk rilevanti per la domanda. Vedi [RAG](../sviluppo/rag.md).

```
Query: "Qual è la policy di backup?"
↓
Embedding della query
↓
Similarity search su vector DB (migliaia di chunk)
↓
Top-K chunk rilevanti (~5-10)
↓
Inseriti nel contesto (pochi KB invece di MB)
```

### 5.3 Summarization Progressiva

Per sequenze molto lunghe (conversazioni, stream di eventi), mantieni un sommario aggiornato invece dell'intera storia.

```python
async def update_conversation_summary(
    client,
    current_summary: str,
    new_messages: list[dict],
    model: str = "claude-3-5-haiku-20241022"
) -> str:
    """Aggiorna il sommario della conversazione con i nuovi messaggi."""
    prompt = f"""
Hai questo sommario della conversazione precedente:
<summary>
{current_summary}
</summary>

Questi sono i nuovi messaggi:
<new_messages>
{format_messages(new_messages)}
</new_messages>

Aggiorna il sommario incorporando le informazioni rilevanti dei nuovi messaggi.
Mantieni il sommario conciso (max 500 parole) ma completo degli aspetti importanti.
"""
    response = await client.messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

### 5.4 Hierarchical Context

Per documenti strutturati (libri, documentazione), usa prima un livello alto (indice, sommari) poi entra nel dettaglio solo dove necessario.

```
Livello 1: "Cerca il capitolo rilevante"
           Input: solo titoli e sommari dei capitoli (~2K token)
           Output: capitolo X è rilevante

Livello 2: "Trova la sezione specifica"
           Input: solo il capitolo X (~10K token)
           Output: sezione 3.2 è rilevante

Livello 3: "Rispondi alla domanda"
           Input: solo la sezione 3.2 (~2K token)
           Output: risposta precisa
```

### 5.5 Context Compression

Tecniche per ridurre il numero di token mantenendo le informazioni essenziali:

```python
# Rimozione di spazi/newline ridondanti
def normalize_whitespace(text: str) -> str:
    import re
    text = re.sub(r'\n{3,}', '\n\n', text)   # max 2 newline consecutivi
    text = re.sub(r' {2,}', ' ', text)        # max 1 spazio
    text = text.strip()
    return text

# Estrazione delle righe più importanti dai log
def extract_error_lines(log: str, max_lines: int = 50) -> str:
    """Estrai solo righe ERROR, CRITICAL, WARN e le ultime N righe."""
    lines = log.split('\n')
    important = [l for l in lines if any(kw in l for kw in ['ERROR', 'CRITICAL', 'WARN', 'Exception', 'Fatal'])]
    tail = lines[-20:]  # ultime 20 righe sempre
    combined = list(dict.fromkeys(important + tail))  # dedup preservando ordine
    return '\n'.join(combined[:max_lines])
```

## 6. Prompt Caching (Anthropic)

Il prompt caching di Anthropic permette di pagare 90% in meno per i token del system prompt o di prefissi statici lunghi, riciclandoli tra richieste consecutive.

```python
import anthropic

client = anthropic.Anthropic()

# Con prompt caching: il system prompt viene cached
# La prima richiesta è normale, le successive pagano solo $0.30/M (vs $3.00/M)
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "Sei un esperto DevOps. " + load_long_documentation(),  # ~10K token
            "cache_control": {"type": "ephemeral"}  # 5 minuti di cache
        }
    ],
    messages=[
        {"role": "user", "content": "Come configuro un Ingress NGINX?"}
    ]
)

# Verifica uso cache
print(f"Input tokens: {response.usage.input_tokens}")
print(f"Cache creation: {response.usage.cache_creation_input_tokens}")
print(f"Cache read: {response.usage.cache_read_input_tokens}")
# Se cache_read > 0, hai pagato 90% in meno per quei token
```

**Regole del prompt caching:**
- Il prefisso da cachare deve essere identico byte-per-byte tra le richieste
- Il `cache_control` marker deve essere sullo stesso breakpoint nella struttura del messaggio
- La cache dura 5 minuti per default (ephemeral)
- Massimo 4 breakpoints di cache per richiesta
- Risparmio: token in cache costano 10% del prezzo normale (90% di sconto)

## 7. Sliding Window Attention

Mistral 7B e alcune varianti architetturali usano Sliding Window Attention (SWA): ogni token può attendere solo agli W token precedenti (es. W=4096), non all'intera sequenza.

```
Sequenza: tok1, tok2, ..., tok10000
Window size W = 4096

tok5000 può attendere a: tok4997 ... tok5000  (solo W=4096 token)
tok5000 NON può attendere a: tok1 ... tok4996

Pro: VRAM per KV cache = O(W) invece di O(seq_len) — molto più efficiente
Con: informazioni lontane nel passato sono inaccessibili direttamente
```

Mistral usa anche Layer Attention Alternata: alcuni layer hanno SWA, altri hanno Full Attention (permettendo attenzione globale a layer alterni).

## Best Practices

- **Struttura il prompt strategicamente**: informazione critica all'inizio (dopo il system) o alla fine (prima della domanda), non nel mezzo.
- **Usa RAG invece di full-context**: per knowledge base grandi, RAG è più preciso e molto più economico del riempire la context window.
- **Monitora la lunghezza dell'input in produzione**: imposta alert quando l'input supera una soglia (es. 70% della context window) per rilevare anomalie.
- **Implementa il prompt caching**: se usi system prompt lunghi o context statici ripetuti, il caching riduce i costi del 70-90%.
- **Testa con "needle in haystack"**: non assumere che il modello usi uniformemente il contesto. Verifica empiricamente per il tuo caso d'uso.
- **Sliding window per applicazioni real-time**: in applicazioni con stream di eventi, mantieni solo una finestra recente di contesto invece di tutto lo storico.

## Troubleshooting

### Scenario 1 — Il modello tronca silenziosamente l'input

**Sintomo:** Le risposte del modello sembrano ignorare informazioni fornite nel prompt. Nessun errore viene restituito dall'API.

**Causa:** L'input supera la context window del modello. La maggior parte dei provider tronca i token in eccesso (spesso dall'inizio) senza lanciare eccezioni.

**Soluzione:** Contare i token prima dell'invio e implementare una guardia esplicita.

```python
import anthropic

client = anthropic.Anthropic()

def safe_create(messages: list, system: str, model: str = "claude-3-5-sonnet-20241022", max_context: int = 180_000):
    """Lancia eccezione esplicita se l'input supera il limite."""
    # Stima token: ~4 caratteri per token (approssimazione)
    total_chars = sum(len(m["content"]) for m in messages) + len(system)
    estimated_tokens = total_chars // 4

    if estimated_tokens > max_context:
        raise ValueError(
            f"Input stimato ~{estimated_tokens} token supera il limite {max_context}. "
            "Considera chunking, RAG o summarization."
        )

    return client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=messages
    )
```

---

### Scenario 2 — OOM / CUDA out of memory con context lunghi

**Sintomo:** Inferenza locale con modelli open source (Llama, Mistral) termina con `CUDA out of memory` su input lunghi che funzionavano con input corti.

**Causa:** Il KV cache cresce linearmente con la lunghezza del contesto. Per Llama 3.1 70B, 128K token richiedono ~40GB aggiuntivi di VRAM solo per il cache.

**Soluzione:** Ridurre la context window massima in fase di caricamento del modello o usare quantizzazione del KV cache.

```bash
# Con vLLM: limitare la context window e usare KV cache quantizzato
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-70B-Instruct \
  --max-model-len 32768 \          # riduci da 128K a 32K
  --kv-cache-dtype fp8 \           # quantizza KV cache (fp16 → fp8, -50% VRAM)
  --gpu-memory-utilization 0.90    # usa 90% della VRAM disponibile

# Con Ollama: controllare il parametro num_ctx
ollama run llama3.1 --num_ctx 16384
```

---

### Scenario 3 — Il prompt caching non riduce i costi attesi

**Sintomo:** I `cache_read_input_tokens` nell'usage response sono sempre 0 anche dopo più richieste consecutive con lo stesso system prompt.

**Causa:** Il contenuto del prefisso cachato non è byte-for-byte identico tra le richieste (spazio extra, ordine diverso dei campi, contenuto dinamico inserito prima del breakpoint).

**Soluzione:** Isolare la parte statica del system prompt, verificare l'identità esatta e posizionare il `cache_control` marker dopo il contenuto invariante.

```python
import anthropic

client = anthropic.Anthropic()

# SBAGLIATO: il testo varia per ogni richiesta → cache miss
def bad_request(user_id: str, docs: str):
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": f"User: {user_id}\n" + docs,  # user_id cambia → cache miss!
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": "..."}]
    )

# CORRETTO: separa parte statica da parte dinamica
def good_request(user_id: str, docs: str):
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": docs,                         # parte statica → cachata
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"Utente corrente: {user_id}" # parte dinamica → non cachata
            }
        ],
        messages=[{"role": "user", "content": "..."}]
    )

# Debug: verifica l'uso della cache nella risposta
response = good_request("user123", load_docs())
usage = response.usage
print(f"Cache creation: {usage.cache_creation_input_tokens}")
print(f"Cache read:     {usage.cache_read_input_tokens}")  # deve essere > 0 dalla seconda chiamata
```

---

### Scenario 4 — Qualità degradata con contesti molto lunghi ("Lost in the Middle")

**Sintomo:** Il modello ignora informazioni rilevanti fornite nel contesto, nonostante siano presenti e il contesto sia entro il limite della window. Il problema peggiora con contesti più lunghi.

**Causa:** Primacy/recency bias: i modelli performano peggio quando l'informazione critica è posizionata al centro della context window (Liu et al., 2023).

**Soluzione:** Riposizionare l'informazione critica all'inizio o alla fine del contesto. Verificare con il "Needle in a Haystack" test.

```python
def build_optimized_prompt(
    critical_info: str,
    background_docs: list[str],
    user_question: str
) -> list[dict]:
    """
    Struttura il prompt per massimizzare il recall dell'informazione critica.
    L'info critica viene messa all'inizio (primacy) e ripetuta alla fine (recency).
    """
    docs_text = "\n\n---\n\n".join(background_docs)

    return [
        {
            "role": "user",
            "content": (
                # ← PRIMACY: info critica subito dopo il system
                f"Informazione chiave da tenere in considerazione:\n{critical_info}\n\n"
                f"Documenti di contesto:\n{docs_text}\n\n"
                # ← RECENCY: domanda alla fine, richiama l'info critica
                f"Domanda (considera l'informazione chiave sopra indicata): {user_question}"
            )
        }
    ]

# Test empirico: "Needle in a Haystack"
def needle_in_haystack_test(client, needle: str, haystack_chunks: list[str], position: int):
    """Inserisce il needle in una posizione specifica e verifica se il modello lo trova."""
    chunks = haystack_chunks.copy()
    chunks.insert(position, f"INFORMAZIONE IMPORTANTE: {needle}")
    context = "\n\n".join(chunks)
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=200,
        messages=[{"role": "user", "content": f"{context}\n\nQual è l'informazione importante?"}]
    )
    found = needle.lower() in response.content[0].text.lower()
    print(f"Position {position}/{len(haystack_chunks)}: {'✓ Found' if found else '✗ Lost'}")
    return found
```

## Riferimenti

- [Lost in the Middle: How Language Models Use Long Contexts (Liu et al., 2023)](https://arxiv.org/abs/2307.03172) — Studio empirico sul primacy/recency bias
- [Extending Context Window of Large Language Models via Positional Interpolation](https://arxiv.org/abs/2306.15595) — Tecniche di estensione context window
- [YaRN: Efficient Context Window Extension (Peng et al., 2023)](https://arxiv.org/abs/2309.00071) — Metodo usato da Llama 3.1 per 128K context
- [Anthropic Prompt Caching Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — Guida ufficiale caching
- [FlashAttention-2 (Dao, 2023)](https://arxiv.org/abs/2307.08691) — Implementazione efficiente dell'attention per context lunghi
