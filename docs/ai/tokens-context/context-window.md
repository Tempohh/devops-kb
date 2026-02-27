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
last_updated: 2026-02-27
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

## Riferimenti

- [Lost in the Middle: How Language Models Use Long Contexts (Liu et al., 2023)](https://arxiv.org/abs/2307.03172) — Studio empirico sul primacy/recency bias
- [Extending Context Window of Large Language Models via Positional Interpolation](https://arxiv.org/abs/2306.15595) — Tecniche di estensione context window
- [YaRN: Efficient Context Window Extension (Peng et al., 2023)](https://arxiv.org/abs/2309.00071) — Metodo usato da Llama 3.1 per 128K context
- [Anthropic Prompt Caching Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — Guida ufficiale caching
- [FlashAttention-2 (Dao, 2023)](https://arxiv.org/abs/2307.08691) — Implementazione efficiente dell'attention per context lunghi
