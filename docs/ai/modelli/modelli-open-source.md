---
title: "Modelli Open Source / Open Weight"
slug: modelli-open-source
category: ai
tags: [open-source, llama, mistral, gemma, qwen, deepseek, ollama, quantization]
search_keywords: [open weight model, Llama 4, Llama 3, Mistral Large 3, Mixtral MoE, Gemma 3, Gemma 4, Qwen3, DeepSeek V3.2, DeepSeek V4, DeepSeek R1, Phi-4, Ollama, llama.cpp, GGUF, GPTQ, AWQ, quantizzazione, local inference, self-hosted LLM, on-premise AI]
parent: ai/modelli/_index
related: [ai/modelli/scelta-modello, ai/mlops/model-serving, ai/mlops/infrastruttura-gpu, ai/training/fine-tuning]
official_docs: https://ollama.com/library
status: reviewed
difficulty: intermediate
last_updated: 2026-09-11
last_verified: 2026-09-11
---

# Modelli Open Source / Open Weight

## Panoramica

I modelli "open weight" rendono pubblici i pesi del modello addestrato, permettendo di scaricarli, eseguirli localmente, fare fine-tuning e deployarli su infrastruttura propria. Questo si contrappone ai modelli closed (Claude, GPT-5) accessibili solo tramite API. La distinzione "open weight" vs "open source" è importante: i modelli open source condividono anche il codice di training e i dati, mentre la maggior parte dei modelli "open" condivide solo i pesi.

Il vantaggio principale dell'open weight è il controllo totale: privacy dei dati, nessuna dipendenza da terze parti, possibilità di fine-tuning su dati proprietari, e costo variabile in base all'utilizzo invece che per token. Lo svantaggio è l'onere operativo: serve infrastruttura GPU, expertise in ML, e le performance sono inferiori ai migliori modelli closed per task complessi.

## Open Weight vs Open Source vs Closed

| Tipo | Pesi | Codice Training | Dati Training | Esempio |
|------|------|-----------------|---------------|---------|
| **Closed** | No | No | No | Claude, GPT-5, Gemini |
| **Open Weight** | Si | No/Parziale | No | Llama 4, Mistral, Gemma |
| **Open Source** | Si | Si | Si/Parziale | OLMo, Falcon, BLOOM |

!!! warning "Licenze — leggere sempre"
    "Open" non significa necessariamente "libero per uso commerciale". Llama 4 usa la Llama 4 Community License, che limita l'uso per servizi con >700M utenti mensili attivi (serve una licenza separata da Meta). Mistral, invece, dalla generazione Large 3/Small 4 è passata ad Apache 2.0 su gran parte della gamma. Sempre verificare la licenza prima del deployment in produzione.

## Llama 4 (Meta)

Llama 4 (agosto 2026) è la generazione attuale della famiglia Llama, nativamente multimodale (testo, immagini, audio/video) fin dal training, a differenza di Llama 3 dove il supporto immagini era stato aggiunto in un secondo momento. Usa architettura Mixture of Experts.

| Variante | Parametri Totali | Parametri Attivi | Context | Use Case |
|----------|------------------|-------------------|---------|---------|
| Llama 4 Scout | 109B (16 esperti) | 17B | 10M | Context lunghissimo, il più grande dell'ecosistema open |
| Llama 4 Maverick | 400B (128 esperti) | 17B | 1M | Frontier open weight, multimodale |
| Llama 4 Behemoth | ~2T (teacher, non rilasciato pubblicamente) | — | — | Modello usato per la distillazione di Scout/Maverick |

**Licenza:** Llama 4 Community License — libero per la maggior parte degli usi commerciali, limitazioni per servizi con >700M MAU (serve licenza separata da Meta).

!!! note "Llama 3 resta rilevante"
    La generazione Llama 3.1/3.2/3.3 (8B, 70B, 405B, varianti edge 1B/3B e multimodali 11B/90B) è ancora ampiamente distribuita, ben documentata e più leggera da eseguire in locale rispetto a Llama 4. Per deployment con vincoli di VRAM stretti o dove il context multi-milione non serve, resta una scelta valida.

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

141B parametri totali, ~39B attivi. 64K context. Architettura ormai superata dalle generazioni successive, ma ancora in uso per deployment esistenti.

### Mistral Large 3 e Small 4 (generazione attuale)

Da fine 2025 Mistral ha spostato l'intera linea flagship su licenza **Apache 2.0**, superando la vecchia licenza proprietaria MRL di Mistral Large 2.

| Modello | Parametri Totali | Parametri Attivi | Context | Licenza |
|---------|-------------------|-------------------|---------|---------|
| Mistral Large 3 (dic 2025) | 675B (MoE granulare) | 41B | 256K | Apache 2.0 |
| Mistral Small 4 (mar 2026) | 24B (denso) | — | 128K | Apache 2.0 |

Mistral Large 3 è quindi, a differenza di Mistral Large 2, pienamente open weight e riutilizzabile in produzione senza restrizioni di licenza.

## Gemma 3 / Gemma 4 (Google)

Gemma 2 è stata superata da Gemma 3 (marzo 2025) e poi da Gemma 4 (aprile 2026), che hanno risolto il principale limite della generazione 2 — il context window ridotto — e aggiunto multimodalità.

| Variante | Parametri | Context | Note |
|----------|-----------|---------|------|
| Gemma 3 1B / 270M | 1B / 270M | 32K | Micro, on-device |
| Gemma 3 4B / 12B / 27B | 4B–27B | 128K | Multimodale (testo + immagini), 140+ lingue |
| Gemma 4 E2B / E4B | 2B–4B | 128K | Multimodale con audio |
| Gemma 4 12B / 26B-A4B / 31B | 12B–31B | 256K | Near-frontier per modelli consumer, MoE su 26B-A4B |

**Innovazioni architetturali (ereditate da Gemma 2 e ampliate):**
- Sliding Window Attention alternata con Global Attention
- Logit soft-capping (stabilità training)
- Knowledge distillation: i modelli piccoli sono distillati da modelli più grandi
- Da Gemma 3: input multimodale (testo + immagini); da Gemma 4: anche audio sui modelli E2B/E4B/12B

**Licenza:** Google Gemma Terms of Use — uso commerciale consentito.

## Qwen3 (Alibaba)

Qwen 2.5 è stata soppiantata da Qwen3, con dual-mode "thinking/non-thinking" nello stesso modello e supporto esteso a 100+ lingue. Alibaba ha poi iterato rapidamente nel 2026 con Qwen3.5, 3.6, 3.7 e 3.8 (in parte open weight, in parte proprietari Max/Plus/Flash).

| Variante | Parametri | Context | Note |
|----------|-----------|---------|------|
| Qwen3 0.6B / 1.7B / 4B | 0.6B–4B | 32K | Micro/edge/mobile |
| Qwen3 8B / 14B / 32B (denso) | 8B–32B | 128K | Consumer/workstation |
| Qwen3-30B-A3B (MoE) | 30B totali, 3B attivi | 128K | Efficienza MoE su hardware consumer |
| Qwen3-235B-A22B (MoE) | 235B totali, 22B attivi | 128K | Frontier open weight |
| Qwen3-Coder / Qwen3-Max (varianti successive) | variabile | 128K+ | Specializzato coding; Max/Plus/Flash sono per lo più proprietari via API |

**Licenza:** Apache 2.0 per l'intera linea Qwen3 open weight (dense e MoE).

## DeepSeek: da V3/R1 a V3.2 e V4

DeepSeek è un'azienda cinese che ha rilasciato modelli con performance frontier a costi di training drasticamente ridotti. La linea V3 (general-purpose) e R1 (reasoning) del 2024-2025 sono state superate da V3.1/V3.2 (2025) e infine unificate in V4 (aprile 2026).

### DeepSeek V3 (2024) e R1 (gen 2025) — generazione precedente

- **DeepSeek V3**: 671B parametri totali, 37B attivi (MoE con 256 esperti, 8 attivi per token); training cost ~$6M; Multi-Token Prediction (MTP)
- **DeepSeek R1**: modello di reasoning con lunghe chain-of-thought, training con RL puro senza SFT iniziale; R1-Distill in versioni 7B/14B/32B/70B
- Restano ampiamente usate per il distillato R1 (ancora un riferimento per i modelli di reasoning piccoli), ma la linea principale è stata soppiantata dalle versioni successive.

### DeepSeek V3.2 (dic 2025)

- Stessa base architetturale di V3, con l'aggiunta di **DeepSeek Sparse Attention (DSA)**: indexer + selezione fine-grained dei token per efficienza su context lunghi
- Context window: 163.840 token
- **Licenza**: MIT (più permissiva della DeepSeek License precedente)

### DeepSeek V4 (apr 2026) — generazione attuale

- Unifica per la prima volta le linee V-series (general) e R-series (reasoning) in un unico modello che alloca dinamicamente la profondità di ragionamento in base al task
- **V4-Flash**: 284B totali, 13B attivi — **V4-Pro**: 1.6T totali, 49B attivi
- Attenzione ibrida (Compressed Sparse Attention + Heavily Compressed Attention) per context fino a 1M token
- **Licenza**: MIT
- Aggiornamento successivo: **V4.1-Flash** (set 2026), che supera V4-Pro su performance/costo/velocità per molti carichi di lavoro

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
- La famiglia si è ampliata con **Phi-4-reasoning** / **Phi-4-reasoning-plus** (focus su matematica/reasoning), **Phi-4-mini** (3.8B, testuale) e **Phi-4-multimodal** (speech + vision + testo) — tutti MIT, dimensioni tra 3.8B e 15B

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
- **Verifica la licenza**: Llama, Gemma hanno licenze proprietarie con soglie MAU; Mistral (da Large 3/Small 4) e Qwen3 sono interamente Apache 2.0, la più permissiva.
- **Modelli specializzati**: per coding usa Qwen3-Coder, per reasoning usa DeepSeek V4 (o R1-Distill per footprint ridotto), per multilingua usa Qwen3 o BLOOM.

## Troubleshooting

### Scenario 1 — Ollama non usa la GPU (inferenza lenta su CPU)

**Sintomo**: `ollama run` impiega minuti invece di secondi; `nvidia-smi` non mostra utilizzo GPU durante l'inferenza.

**Causa**: Il driver NVIDIA non è rilevato da Ollama, oppure la versione di CUDA è incompatibile. Su Windows, può essere necessario installare la versione Ollama con supporto CUDA esplicito.

**Soluzione**: Verificare che i driver NVIDIA siano aggiornati (≥525) e che CUDA sia installato. Controllare i log di Ollama per messaggi su GPU detection.

```bash
# Verifica che Ollama veda la GPU
ollama run llama3.1:8b --verbose 2>&1 | grep -i gpu

# Controlla i log di sistema Ollama
# Linux/macOS:
journalctl -u ollama -f
# Windows: Event Viewer → Applications → Ollama

# Forza l'uso GPU specificando il numero di layer da offloadare
OLLAMA_NUM_GPU=35 ollama run llama3.1:8b  # Linux/macOS
# Su Windows (PowerShell):
$env:OLLAMA_NUM_GPU=35; ollama run llama3.1:8b

# Controlla la VRAM disponibile e i layer caricati su GPU
ollama ps  # mostra i modelli in esecuzione e la VRAM usata
```

---

### Scenario 2 — OOM (Out of Memory) durante il caricamento del modello

**Sintomo**: `ollama run` o `llama-cli` terminano con errore `CUDA out of memory`, `failed to allocate tensor`, o il processo viene killato dall'OS.

**Causa**: Il modello (anche quantizzato) supera la VRAM disponibile. Un modello 7B in Q4_K_M richiede ~4.5 GB; in FP16 ne richiede ~14 GB.

**Soluzione**: Passare a una quantizzazione più aggressiva, usare un modello più piccolo, oppure abilitare l'offload parziale su RAM (più lento).

```bash
# Controlla la VRAM disponibile prima di caricare
nvidia-smi --query-gpu=memory.total,memory.free --format=csv

# Usa una quantizzazione più leggera
ollama pull llama3.1:8b-instruct-q4_0   # invece di q8_0
ollama pull llama3.1:8b-instruct-q2_K   # se VRAM < 4GB

# Con llama.cpp: offload parziale su RAM (layer GPU limitati)
./build/bin/llama-cli \
  -m model-Q4_K_M.gguf \
  --n-gpu-layers 20 \   # carica solo 20 layer su GPU, resto su CPU
  -p "Il tuo prompt"

# Verifica VRAM usata dopo il caricamento
ollama ps
```

---

### Scenario 3 — Qualità degradata con quantizzazione aggressiva

**Sintomo**: Il modello con Q2_K o Q3_K produce risposte incoerenti, ripetizioni, o allucinazioni evidenti assenti nelle versioni FP16/Q8.

**Causa**: La quantizzazione a 2-3 bit causa perdita significativa di precisione nei pesi — i modelli piccoli (7B) soffrono più dei modelli grandi (70B) perché hanno meno ridondanza.

**Soluzione**: Passare almeno a Q4_K_M (punto dolce qualità/VRAM). Per task critici, usare Q6_K o Q8_0. I modelli grandi (70B) tollerano meglio le quantizzazioni aggressive.

```bash
# Confronto qualitativo: stessa domanda con diverse quantizzazioni
for quant in q2_K q4_K_M q6_K q8_0; do
  echo "=== $quant ==="
  ollama pull llama3.1:8b-instruct-$quant 2>/dev/null
  echo "Spiega il CAP theorem in una frase" | ollama run llama3.1:8b-instruct-$quant
done

# Regola pratica: non scendere sotto Q4 per modelli ≤13B
# Per modelli 70B+ Q3_K_M è ancora accettabile
# IQ4_XS offre qualità simile a Q4_K_M con VRAM leggermente inferiore
ollama pull llama3.1:8b-instruct-iq4_xs
```

---

### Scenario 4 — Modelfile ignorato o parametri non applicati

**Sintomo**: Dopo `ollama create`, il modello non usa il system prompt o i parametri (temperature, num_ctx) definiti nel Modelfile.

**Causa**: Il nome del modello custom in `ollama run` non corrisponde al nome usato in `ollama create`, oppure il Modelfile contiene errori di sintassi silenziosi. Il parametro `num_ctx` richiede VRAM sufficiente — Ollama lo riduce silenziosamente se la memoria non è disponibile.

**Soluzione**: Verificare che il modello sia stato creato correttamente con `ollama list` e ispezionare la configurazione effettiva con `ollama show`.

```bash
# Crea il modello dal Modelfile
ollama create devops-assistant -f Modelfile

# Verifica che il modello esista
ollama list | grep devops-assistant

# Ispeziona i parametri effettivamente applicati
ollama show devops-assistant
ollama show devops-assistant --modelfile   # mostra il Modelfile completo
ollama show devops-assistant --parameters  # solo i parametri

# Se num_ctx viene ridotto, verificare VRAM disponibile
# Un context di 8192 token su un 8B Q4 richiede ~1-2 GB extra di VRAM
# Ridurre num_ctx se necessario:
# PARAMETER num_ctx 4096  (invece di 8192)

# Ricreare il modello dopo modifiche al Modelfile
ollama rm devops-assistant
ollama create devops-assistant -f Modelfile
```

## Riferimenti

- [Ollama Library](https://ollama.com/library) — Catalogo modelli per Ollama
- [HuggingFace Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) — Benchmark open models
- [llama.cpp GitHub](https://github.com/ggml-org/llama.cpp) — Inferenza CPU ottimizzata
- [TheBloke HuggingFace](https://huggingface.co/TheBloke) — Repository di modelli GGUF e GPTQ
- [GGUF Quantization Guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/quantization.md) — Dettagli tecnici quantizzazione
