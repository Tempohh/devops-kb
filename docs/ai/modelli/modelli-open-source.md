---
title: "Modelli Open Source / Open Weight"
slug: modelli-open-source
category: ai
tags: [open-source, llama, mistral, gemma, qwen, deepseek, ollama, quantization]
search_keywords: [open weight model, Llama 3, Mistral 7B, Mixtral MoE, Gemma 2, Qwen 2.5, DeepSeek V3, DeepSeek R1, Phi-4, Ollama, llama.cpp, GGUF, GPTQ, AWQ, quantizzazione, local inference, self-hosted LLM, on-premise AI]
parent: ai/modelli/_index
related: [ai/modelli/scelta-modello, ai/mlops/model-serving, ai/mlops/infrastruttura-gpu, ai/training/fine-tuning]
official_docs: https://ollama.com/library
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# Modelli Open Source / Open Weight

## Panoramica

I modelli "open weight" rendono pubblici i pesi del modello addestrato, permettendo di scaricarli, eseguirli localmente, fare fine-tuning e deployarli su infrastruttura propria. Questo si contrappone ai modelli closed (Claude, GPT-4) accessibili solo tramite API. La distinzione "open weight" vs "open source" è importante: i modelli open source condividono anche il codice di training e i dati, mentre la maggior parte dei modelli "open" condivide solo i pesi.

Il vantaggio principale dell'open weight è il controllo totale: privacy dei dati, nessuna dipendenza da terze parti, possibilità di fine-tuning su dati proprietari, e costo variabile in base all'utilizzo invece che per token. Lo svantaggio è l'onere operativo: serve infrastruttura GPU, expertise in ML, e le performance sono inferiori ai migliori modelli closed per task complessi.

## Open Weight vs Open Source vs Closed

| Tipo | Pesi | Codice Training | Dati Training | Esempio |
|------|------|-----------------|---------------|---------|
| **Closed** | No | No | No | Claude, GPT-4, Gemini Pro |
| **Open Weight** | Si | No/Parziale | No | Llama 3, Mistral, Gemma |
| **Open Source** | Si | Si | Si/Parziale | OLMo, Falcon, BLOOM |

!!! warning "Licenze — leggere sempre"
    "Open" non significa necessariamente "libero per uso commerciale". Llama 3 ha una licenza che limita l'uso per servizi con >700M utenti mensili. Mistral Large usa "MRL" (proprietaria). Sempre verificare la licenza prima del deployment in produzione.

## Llama 3 (Meta)

Llama 3 è la famiglia di modelli open weight di riferimento dal 2024. La terza generazione ha fatto un salto qualitativo significativo rispetto a Llama 2.

**Architettura:** Transformer decoder-only con GQA (Grouped Query Attention), RoPE, SwiGLU, RMSNorm. Tokenizer con vocab 128K (il doppio di Llama 2).

| Variante | Parametri | Context | Use Case |
|----------|-----------|---------|---------|
| Llama 3.2 1B | 1B | 128K | Edge, mobile, IoT |
| Llama 3.2 3B | 3B | 128K | On-device, task semplici |
| Llama 3.1 8B | 8B | 128K | Deployment economico, buona qualità |
| Llama 3.1 70B | 70B | 128K | Near-frontier, ottimo rapporto qualità/costo |
| Llama 3.1 405B | 405B | 128K | Frontier open weight |
| Llama 3.2 11B | 11B | 128K | Multimodal (testo + immagini) |
| Llama 3.2 90B | 90B | 128K | Multimodal high-quality |
| Llama 3.3 70B | 70B | 128K | Versione aggiornata 70B (Dec 2024) |

**Licenza:** Llama 3 Community License — libero per la maggior parte degli usi commerciali, limitazioni per servizi molto grandi (>700M MAU).

## Mistral / Mixtral (Mistral AI)

Mistral AI è una startup europea che ha rilasciato modelli con performance/size eccellenti.

### Mistral 7B

Il primo modello (Sept 2023) che ha sorpreso per performance sopra Llama 2 13B con metà dei parametri. Introduce Sliding Window Attention (SWA) per context lunghi e GQA.

```
Architettura Mistral 7B:
- 32 layer Transformer
- Hidden dim: 4096
- Sliding Window Attention: 4096 token finestra locale
- GQA: 8 gruppi KV (efficienza memoria)
- Vocab: 32K
```

### Mistral Nemo 12B (2024)

Sviluppato con NVIDIA. 128K context, tokenizer Tekken con 131K vocab. Ottimo bilanciamento tra dimensione e capacità.

### Mixtral 8×7B — Mixture of Experts

Invece di un unico FFN layer, Mixtral ha 8 "esperti" (FFN separati). Per ogni token, un **router** seleziona i 2 esperti più rilevanti. Risultato: 46.7B parametri totali ma solo ~12.9B attivi per token.

```
Per ogni token:
Input → Router → seleziona 2 esperti su 8
     → Expert 1 output × gate_1 + Expert 2 output × gate_2
     → Output

Vantaggio: qualità da 47B con compute da 13B
Svantaggio: VRAM necessaria per caricare tutti i pesi (ancora 47B)
```

Licenza: Apache 2.0 (pienamente libero per uso commerciale).

### Mixtral 8×22B

141B parametri totali, ~39B attivi. Vicino a GPT-3.5 per qualità. 64K context.

### Mistral Large 2

Il modello flagship di Mistral con ~123B parametri. Non open-weight completo (licenza MRL, uso commerciale ristretto). 128K context.

## Gemma 2 (Google)

Gemma 2 è la famiglia di modelli piccoli ma capaci di Google, ottimizzati per efficienza su hardware consumer.

| Variante | Parametri | Context | Note |
|----------|-----------|---------|------|
| Gemma 2 2B | 2B | 8K | Ideale on-device, Pixel, Android |
| Gemma 2 9B | 9B | 8K | Ottimo per il suo size |
| Gemma 2 27B | 27B | 8K | Near-frontier per modelli consumer |

**Innovazioni architetturali Gemma 2:**
- Sliding Window Attention alternata con Global Attention
- Logit soft-capping (stabilità training)
- Knowledge distillation: i modelli piccoli sono stati distillati da modelli più grandi

!!! note "Context window limitata"
    Gemma 2 ha context window di soli 8K token — molto meno di Llama 3 (128K). Per task con documenti lunghi, Llama 3 è preferibile.

**Licenza:** Google Gemma Terms of Use — uso commerciale consentito.

## Qwen 2.5 (Alibaba)

La famiglia Qwen 2.5 di Alibaba si distingue per performance eccellenti in coding, matematica e lingue diverse dall'inglese (cinese in particolare).

| Variante | Parametri | Context | Note |
|----------|-----------|---------|------|
| Qwen2.5 0.5B | 0.5B | 32K | Micro, on-device |
| Qwen2.5 1.5B | 1.5B | 32K | Edge |
| Qwen2.5 3B | 3B | 32K | Mobile |
| Qwen2.5 7B | 7B | 128K | Consumer GPU |
| Qwen2.5 14B | 14B | 128K | Consumer/workstation |
| Qwen2.5 32B | 32B | 128K | Near-frontier |
| Qwen2.5 72B | 72B | 128K | Frontier open weight |
| Qwen2.5-Coder 32B | 32B | 128K | Specializzato per coding |
| Qwen2.5-Math 72B | 72B | 128K | Specializzato per matematica |

**Licenza:** Apache 2.0 per la maggior parte delle varianti.

## DeepSeek V3 e R1

DeepSeek è un'azienda cinese che ha rilasciato modelli con performance frontier a costi di training drasticamente ridotti.

### DeepSeek V3

- **671B parametri totali, 37B attivi** (MoE con 256 esperti, 8 attivi per token)
- **Training cost**: circa $6M (vs centinaia di milioni per modelli simili)
- **Performance**: vicino o superiore a GPT-4o su molti benchmark
- **Multi-Token Prediction (MTP)**: predice più token futuri simultaneamente
- **Licenza**: DeepSeek License — libero per ricerca, uso commerciale consentito

### DeepSeek R1

Modello di **reasoning** con capacità simili a o1 di OpenAI:
- Genera lunghe chain-of-thought prima della risposta finale
- Training con RL puro senza SFT iniziale (innovazione tecnica rilevante)
- Eccelle su matematica, coding, problemi scientifici
- R1-Distill: versioni distillate in modelli più piccoli (7B, 14B, 32B, 70B) che mantengono le capacità di reasoning

```python
# Esempio interazione con DeepSeek R1 via Ollama
# Il modello genera <think>...</think> prima della risposta
ollama pull deepseek-r1:7b
ollama run deepseek-r1:7b "Risolvi: se x² + 5x + 6 = 0, trova le radici"
# Output include blocco <think> con ragionamento step-by-step
```

## Phi-4 (Microsoft)

- **14B parametri**, context 16K
- Addestrato su dati sintetici di alta qualità (approccio "quality over quantity")
- Performance sorprendenti per la sua dimensione, sopra modelli 2-3× più grandi
- **Licenza**: MIT — pienamente libero

## Deployment Locale

### Ollama — Il Modo Più Semplice

Ollama permette di scaricare ed eseguire modelli LLM localmente con un singolo comando.

```bash
# Installazione (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh
# Windows: installer da ollama.com

# Scaricare e avviare un modello
ollama pull llama3.1:8b          # scarica il modello
ollama pull mistral:7b           # Mistral 7B
ollama pull qwen2.5:14b          # Qwen 2.5 14B
ollama pull deepseek-r1:7b       # DeepSeek R1 distill 7B

# Esecuzione interattiva
ollama run llama3.1:8b

# API REST compatibile con OpenAI
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Spiega Kubernetes in 3 righe"}]
  }'

# Elenco modelli disponibili
ollama list

# Eliminare un modello
ollama rm llama3.1:8b
```

```python
# Uso via Python con openai library
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # placeholder
)

response = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[{"role": "user", "content": "Genera un Dockerfile per un'app Node.js"}]
)
print(response.choices[0].message.content)
```

**Modelfile — personalizzazione del modello:**

```dockerfile
# Modelfile per un assistant DevOps specializzato
FROM llama3.1:8b

SYSTEM """
Sei un esperto DevOps senior. Rispondi sempre con esempi pratici e codice funzionante.
Quando suggerisci comandi, usa sempre il blocco ```bash```.
Lingua: italiano con terminologia tecnica in inglese.
"""

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
```

```bash
ollama create devops-assistant -f Modelfile
ollama run devops-assistant
```

### llama.cpp — Inferenza CPU e Quantizzazione

llama.cpp permette di eseguire LLM quantizzati anche su CPU (molto più lento della GPU ma senza requisiti hardware speciali).

```bash
# Build
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON  # con supporto CUDA
cmake --build build --config Release -j$(nproc)

# Download modello quantizzato GGUF da HuggingFace
# Esempio: Llama 3.1 8B Q4_K_M (qualità/VRAM ottimale per Q4)
wget https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf

# Inferenza
./build/bin/llama-cli \
  -m Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  -n 512 \
  -p "Spiega il pattern Circuit Breaker in microservizi:"

# Server OpenAI-compatible
./build/bin/llama-server \
  -m Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -c 4096  # context size
```

## Quantizzazione

La quantizzazione riduce la precisione dei pesi del modello da FP32/FP16 a formati più compatti (INT8, INT4, INT2), riducendo VRAM e aumentando la velocità di inferenza a scapito di una piccola perdita di qualità.

### GGUF (formato llama.cpp)

Il formato GGUF (GGML Universal File) è lo standard de facto per la distribuzione di modelli quantizzati per inferenza locale.

| Quantizzazione | Bit/peso | VRAM (8B) | Qualità | Uso Consigliato |
|---------------|----------|-----------|---------|-----------------|
| **Q8_0** | 8 bit | ~8.5GB | Quasi identica a FP16 | Massima qualità, GPU 12GB+ |
| **Q6_K** | 6 bit | ~6.1GB | Eccellente | GPU 8GB, minima perdita |
| **Q5_K_M** | 5 bit | ~5.3GB | Molto buona | GPU 8GB, buon bilanciamento |
| **Q4_K_M** | 4 bit | ~4.8GB | Buona | **Best default** — GPU 6GB |
| **Q3_K_M** | 3 bit | ~3.9GB | Accettabile | GPU 4GB, qualità ok |
| **Q2_K** | 2 bit | ~3.1GB | Degradata | Ultimi 4GB disponibili |
| **IQ4_XS** | ~4 bit | ~4.4GB | Buona (IQ = importance-aware) | Alternativa Q4_K_M |

**Convenzione nomi GGUF:**
- `Q4_K_M`: Q=quantizzazione, 4=bit, K=K-quant (tecnica avanzata), M=Medium (bilanciamento)
- `_S` = Small (qualità leggermente inferiore, meno VRAM)
- `_L` = Large (qualità superiore, più VRAM)

### GPTQ (GPU-optimized)

Quantizzazione post-training calibrata su un dataset. Più precisa di GGUF per GPU, richiede PyTorch.

```bash
pip install auto-gptq optimum

from auto_gptq import AutoGPTQForCausalLM
model = AutoGPTQForCausalLM.from_quantized(
    "TheBloke/Llama-3.1-8B-Instruct-GPTQ",
    device="cuda:0",
    use_triton=True
)
```

### AWQ (Activation-aware Weight Quantization)

Più accurata di GPTQ, preserva i pesi importanti (quelli con alta attivazione) ad alta precisione.

```bash
pip install awq

from awq import AutoAWQForCausalLM
model = AutoAWQForCausalLM.from_quantized(
    "casperhansen/llama-3-8b-instruct-awq",
    fuse_layers=True
)
```

### Trade-off Riassuntivo

| Formato | Hardware | Velocità | Qualità | Flessibilità |
|---------|----------|----------|---------|-------------|
| FP16 | GPU (high VRAM) | Alta | Baseline | Alta |
| GPTQ | GPU | Alta | Ottima | Media |
| AWQ | GPU | Alta | Ottima | Media |
| GGUF Q4_K_M | CPU o GPU | Media (CPU lenta) | Buona | Alta |
| GGUF Q8_0 | GPU | Alta | Quasi FP16 | Alta |

## VRAM Necessaria per Modello

| Modello | FP16 | Q4_K_M | Q8_0 |
|---------|------|--------|------|
| 3B | ~6 GB | ~2 GB | ~3 GB |
| 7-8B | ~14 GB | ~4.5 GB | ~8 GB |
| 13B | ~26 GB | ~8 GB | ~13 GB |
| 34B | ~68 GB | ~20 GB | ~34 GB |
| 70B | ~140 GB | ~40 GB | ~70 GB |
| 405B | ~810 GB | ~220 GB | ~405 GB |

## Best Practices

- **Inizia con Ollama per sviluppo**: massima semplicità, gestione automatica del download e quantizzazione.
- **llama.cpp per deployment CPU**: se non hai GPU, Q4_K_M offre il miglior rapporto qualità/velocità.
- **vLLM per produzione**: per serving ad alta concorrenza, usa vLLM (vedi [model-serving](../mlops/model-serving.md)).
- **Q4_K_M come default**: per la maggior parte degli usi, Q4_K_M è il punto dolce tra qualità e risorse.
- **Verifica la licenza**: Llama 3, Mistral, Gemma hanno licenze diverse. Apache 2.0 (Mistral 7B, Qwen) è la più permissiva.
- **Modelli specializzati**: per coding usa Qwen2.5-Coder, per reasoning usa DeepSeek R1, per multilingua usa Qwen o BLOOM.

## Riferimenti

- [Ollama Library](https://ollama.com/library) — Catalogo modelli per Ollama
- [HuggingFace Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) — Benchmark open models
- [llama.cpp GitHub](https://github.com/ggml-org/llama.cpp) — Inferenza CPU ottimizzata
- [TheBloke HuggingFace](https://huggingface.co/TheBloke) — Repository di modelli GGUF e GPTQ
- [GGUF Quantization Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/quantization.md) — Dettagli tecnici quantizzazione
