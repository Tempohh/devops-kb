---
title: "Valutazione LLM — Benchmark e Evals"
slug: valutazione
category: ai
tags: [evaluation, benchmark, mmlu, humaneval, evals, llm-judge]
search_keywords: [valutazione LLM, benchmark AI, MMLU, HumanEval, MATH, GPQA, MT-Bench, LMSYS Arena, LLM-as-judge, evals custom, RAGAS evaluation, promptfoo, braintrust, langsmith, weave W&B, evaluazione modelli, model evaluation framework, SWE-bench]
parent: ai/training/_index
related: [ai/training/_index, ai/training/fine-tuning, ai/modelli/scelta-modello, ai/sviluppo/rag, ai/mlops/pipeline-ml]
official_docs: https://docs.ragas.io/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Valutazione LLM — Benchmark e Evals

## Panoramica

La valutazione degli LLM è fondamentalmente diversa dalla valutazione dei sistemi ML classici: l'output è testo libero, spesso non c'è una risposta unica corretta, e la qualità è in parte soggettiva. Nonostante questi limiti, una valutazione rigorosa è indispensabile sia per scegliere il modello giusto, sia per misurare il miglioramento dopo un fine-tuning, sia per monitorare la qualità in produzione.

Esistono due categorie di valutazione: i **benchmark standardizzati** (test fissi usati per confrontare modelli tra loro) e gli **evals custom** (test specifici per il tuo task reale). I benchmark pubblicati sono utili per una valutazione iniziale, ma non sostituiscono mai la valutazione sul proprio task. Un modello con MMLU 90% può essere molto peggiore di uno con MMLU 85% sul tuo specifico caso d'uso.

## 1. Benchmark Standardizzati

### MMLU — Massive Multitask Language Understanding

MMLU misura la conoscenza enciclopedica su 57 soggetti accademici: matematica, scienze, legge, medicina, storia, fisica, etica, e molti altri.

```
Formato: Multiple choice (4 opzioni), 0-shot e 5-shot
Size: 15.908 domande
Split: 57 task × (validation + test)
Punteggio: accuracy (% risposte corrette)

Esempio:
Domanda: "Il protocollo TCP garantisce:
A) Consegna in ordine ma non affidabile
B) Consegna affidabile e in ordine
C) Velocità massima
D) Consegna non affidabile"
Risposta: B
```

```python
# Valutazione MMLU con LM-Evaluation-Harness
# pip install lm-eval
import subprocess

subprocess.run([
    "lm_eval",
    "--model", "hf",
    "--model_args", "pretrained=meta-llama/Meta-Llama-3.1-8B-Instruct",
    "--tasks", "mmlu",
    "--num_fewshot", "5",
    "--batch_size", "8",
    "--output_path", "results/mmlu"
])
```

### HumanEval — Coding Benchmark

HumanEval misura la capacità di completare funzioni Python con descrizione naturale. La metrica è **pass@k**: probabilità che almeno k tentativi generati passino tutti i test.

```
Formato: Completamento funzione Python + docstring
Size: 164 problemi
Metrica: pass@1 (1 tentativo per problema)

Esempio:
def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """
    Check if in given list of numbers, are any two numbers closer to each other
    than given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """
    # Il modello deve completare qui
```

```python
# Calcolo pass@k
import numpy as np
from scipy.special import comb

def pass_at_k(n: int, c: int, k: int) -> float:
    """
    n = numero totale di campioni generati
    c = numero di campioni corretti
    k = numero di tentativi considerati (pass@k)
    """
    if n - c < k:
        return 1.0
    return 1.0 - np.prod([(n - c - i) / (n - i) for i in range(k)])

# Esempio: genero 10 soluzioni per problema, 3 passano i test
# pass@1 = probabilità che almeno 1 soluzione su 1 tentativo sia corretta
print(f"pass@1: {pass_at_k(10, 3, 1):.3f}")  # ~0.30
print(f"pass@5: {pass_at_k(10, 3, 5):.3f}")  # ~0.83
```

### SWE-bench — Real-World Software Engineering

SWE-bench è il benchmark più realistico per coding agents: dati da issue reali di repository GitHub popolari.

```
Formato: (issue GitHub, codebase repository, test di verifica)
Task: il modello deve modificare il codice per risolvere l'issue
Valutazione: i test di regressione devono passare
Size: 2294 task (SWE-bench), 500 (SWE-bench Verified)
Metrica: % di task risolti

Risultati 2024-2025:
- Claude 3.5 Sonnet: ~49% (SWE-bench Verified)
- GPT-4o: ~38%
- Llama 3.1 70B: ~12%
```

### MATH — Competition Mathematics

```
Formato: Problemi matematici competition (AMC, AIME, livello)
Valutazione: exact match della risposta finale
Difficoltà: 5 livelli (Level 1 = facile, Level 5 = AIME)

Punteggi indicativi (2024):
- Gemini 1.5 Pro: ~92%
- GPT-4o: ~90%
- Claude 3.5 Sonnet: ~87%
- Llama 3.1 70B: ~68%
```

### GPQA — Graduate-Level Science Q&A

```
Formato: Multiple choice su argomenti PhD (fisica, chimica, biologia)
Soprannome: "Google-Proof" — risposte non trovabili facilmente online
Size: 448 domande
Difficoltà: anche esperti del dominio rispondono ~65% di media

Punteggi indicativi (2024):
- Claude 3.5 Sonnet: ~59%
- GPT-4o: ~53%
- Humani esperti: ~65%
```

### MT-Bench — Multi-Turn Conversation Quality

```
Formato: 80 domande multi-turn in 8 categorie
Valutatore: GPT-4 assegna un punteggio 1-10
Categorie: writing, roleplay, extraction, reasoning, math, coding, knowledge, STEM

Prompt example (turno 1):
"Compose a haiku that captures the essence of 'kawaii' culture in Japan."

Prompt example (turno 2 — deve ricordare il turno 1):
"Now describe the image you just wrote about as if you were explaining it to someone who has never heard of kawaii."
```

### Tabella Benchmark — Overview

| Benchmark | Focus | Metrica | Link |
|-----------|-------|---------|------|
| MMLU | Conoscenza 57 domini | Accuracy % | [Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) |
| HumanEval | Coding Python | pass@1 | [GitHub](https://github.com/openai/human-eval) |
| SWE-bench | SW Engineering reale | Resolved % | [swebench.com](https://www.swebench.com/) |
| MATH | Matematica competition | Exact match | |
| GPQA | PhD-level science | Accuracy % | |
| MT-Bench | Chat multi-turn | Score 1-10 | |
| LMSYS Arena | Preferenze umane | ELO | [lmsys.org](https://chat.lmsys.org/?leaderboard) |
| BigBench Hard | 23 task difficili | Accuracy | |

## 2. Evals Custom — Il Vero Test

I benchmark pubblici misurano capacità generali. Per decidere quale modello usare nel tuo sistema specifico, costruisci un eval set con i tuoi casi d'uso reali.

### Struttura di un Eval Set

```python
from dataclasses import dataclass, field
from typing import Callable
import json

@dataclass
class EvalCase:
    """Un singolo caso di test per un LLM."""
    id: str
    category: str                           # es. "kubernetes", "security", "debugging"
    difficulty: str                         # "easy", "medium", "hard"
    input: dict                             # {"system": str, "user": str}
    expected: dict                          # criteri di valutazione
    tags: list[str] = field(default_factory=list)

# Esempi per un sistema di code review
eval_cases = [
    EvalCase(
        id="security-001",
        category="security",
        difficulty="hard",
        input={
            "system": "Sei un senior code reviewer. Rispondi in JSON.",
            "user": """Review questo codice:
```python
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return db.execute(query).fetchone()
```"""
        },
        expected={
            "must_contain": ["SQL injection", "parametrized"],
            "must_contain_severity": ["critical", "high"],
            "must_not_contain": ["approvato", "OK", "looks good"],
            "output_is_valid_json": True,
            "json_must_have_keys": ["blocking_issues", "approved"]
        },
        tags=["security", "sql", "python"]
    ),
    EvalCase(
        id="k8s-001",
        category="kubernetes",
        difficulty="medium",
        input={
            "system": "Sei un esperto Kubernetes.",
            "user": "Spiega la differenza tra Deployment e StatefulSet in 3 punti"
        },
        expected={
            "must_contain": ["StatefulSet", "Deployment", "stato", "persistente"],
            "output_min_length": 200,
            "max_sentences_of_hallucination": 0
        },
        tags=["kubernetes", "concepts"]
    )
]
```

### Esecuzione degli Evals

```python
import anthropic
import json
import re
from datetime import datetime

client = anthropic.Anthropic()

def run_eval(eval_case: EvalCase, model: str) -> dict:
    """Esegui un singolo eval e restituisci i risultati."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=eval_case.input.get("system", ""),
            messages=[{"role": "user", "content": eval_case.input["user"]}]
        )
        output = response.content[0].text
    except Exception as e:
        return {"id": eval_case.id, "model": model, "error": str(e), "passed": False}

    # Valutazione
    passed = True
    failures = []
    expected = eval_case.expected

    # Check must_contain
    for term in expected.get("must_contain", []):
        if term.lower() not in output.lower():
            passed = False
            failures.append(f"Manca termine: '{term}'")

    # Check must_not_contain
    for term in expected.get("must_not_contain", []):
        if term.lower() in output.lower():
            passed = False
            failures.append(f"Contiene termine vietato: '{term}'")

    # Check lunghezza minima
    if len(output) < expected.get("output_min_length", 0):
        passed = False
        failures.append(f"Output troppo corto: {len(output)} < {expected['output_min_length']}")

    # Check JSON valido
    if expected.get("output_is_valid_json"):
        try:
            parsed = json.loads(output)
            for key in expected.get("json_must_have_keys", []):
                if key not in parsed:
                    passed = False
                    failures.append(f"JSON manca chiave: '{key}'")
        except json.JSONDecodeError:
            passed = False
            failures.append("Output non è JSON valido")

    return {
        "id": eval_case.id,
        "model": model,
        "category": eval_case.category,
        "difficulty": eval_case.difficulty,
        "passed": passed,
        "failures": failures,
        "output": output,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens
    }

def run_eval_suite(eval_cases: list[EvalCase], models: list[str]) -> dict:
    """Esegui suite completa e genera report comparativo."""
    results = {model: {"passed": 0, "failed": 0, "by_category": {}} for model in models}

    for case in eval_cases:
        for model in models:
            result = run_eval(case, model)
            if result["passed"]:
                results[model]["passed"] += 1
            else:
                results[model]["failed"] += 1
                print(f"FAIL [{model}][{case.id}]: {result['failures']}")

    # Calcola statistiche
    for model in models:
        total = results[model]["passed"] + results[model]["failed"]
        results[model]["pass_rate"] = results[model]["passed"] / total if total > 0 else 0

    return results

# Utilizzo
results = run_eval_suite(
    eval_cases,
    models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
)
print(json.dumps(results, indent=2))
```

## 3. LLM-as-Judge

Usare un LLM (tipicamente Claude o GPT-4) per valutare l'output di un altro LLM. Permette di valutare qualità subjettiva su scala.

```python
def llm_judge_eval(
    judge_model: str,
    question: str,
    response_to_evaluate: str,
    rubric: str,
    reference_answer: str = None
) -> dict:
    """Usa un LLM come giudice per valutare una risposta."""

    judge_prompt = f"""Valuta la seguente risposta su questa domanda tecnica.

<question>
{question}
</question>

<response_to_evaluate>
{response_to_evaluate}
</response_to_evaluate>

{f'<reference_answer>{reference_answer}</reference_answer>' if reference_answer else ''}

<rubric>
{rubric}
</rubric>

Valuta la risposta e rispondi con JSON:
{{
  "score": 1-5,
  "reasoning": "Spiegazione del punteggio (2-3 frasi)",
  "strengths": ["punto di forza 1", "..."],
  "weaknesses": ["punto debole 1", "..."],
  "verdict": "pass" | "fail"
}}

Scala: 1=scarso, 2=insufficiente, 3=sufficiente, 4=buono, 5=eccellente"""

    response = client.messages.create(
        model=judge_model,
        max_tokens=512,
        messages=[{"role": "user", "content": judge_prompt}]
    )

    try:
        return json.loads(response.content[0].text)
    except json.JSONDecodeError:
        return {"error": "Judge non ha restituito JSON valido", "raw": response.content[0].text}

# Rubrica per valutare risposte su argomenti DevOps
DEVOPS_RUBRIC = """
Criteri di valutazione (ognuno 0-1 punto):
1. ACCURATEZZA TECNICA: Le informazioni sono corrette e aggiornate?
2. COMPLETEZZA: Copre tutti gli aspetti importanti della domanda?
3. ESEMPI PRATICI: Include comandi, codice, o esempi concreti dove appropriato?
4. CHIAREZZA: È facile da capire per un ingegnere DevOps di livello medio?
5. ACTIONABILITÀ: Il lettore può agire immediatamente con queste informazioni?

Assegna da 1 a 5 basandoti sul numero di criteri soddisfatti.
"""

# Esempio
judgment = llm_judge_eval(
    judge_model="claude-3-5-sonnet-20241022",  # modello giudice
    question="Come si configura un Horizontal Pod Autoscaler in Kubernetes?",
    response_to_evaluate=model_response,
    rubric=DEVOPS_RUBRIC
)
print(f"Score: {judgment['score']}/5 — Verdict: {judgment['verdict']}")
```

### Bias del LLM-as-Judge

| Bias | Descrizione | Mitigazione |
|------|-------------|-------------|
| **Self-enhancement** | Claude preferisce le risposte di Claude, GPT-4 preferisce le proprie | Usa un judge diverso dal modello valutato |
| **Verbosity bias** | Tende a premiare risposte più lunghe, anche se verbose | Specifica nella rubrica che concisione è un pregio |
| **Position bias** | In confronti, preferisce la prima risposta presentata | Randomizza l'ordine delle risposte da confrontare |
| **Sycophancy** | Tende a concordare con la risposta fornita dall'umano | Usa rubriche oggettive, non chiedere "È buona?" |

## 4. RAGAS — Valutazione RAG Specifica

RAGAS (RAG Assessment) è un framework per valutare sistemi RAG su 4 metriche.

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,      # La risposta è supportata dai documenti recuperati?
    answer_relevancy,  # La risposta è pertinente alla domanda?
    context_precision, # Il contesto recuperato è preciso (poca ridondanza)?
    context_recall,    # Il contesto recuperato contiene tutte le info necessarie?
)
from datasets import Dataset

# Dataset per valutazione RAGAS
ragas_data = {
    "question": [
        "Come si configura un Ingress con TLS in Kubernetes?",
        "Qual è la differenza tra kubectl apply e kubectl create?"
    ],
    "answer": [
        "Per configurare un Ingress con TLS, crea un Secret TLS e referenzialo nell'Ingress spec...",
        "kubectl apply usa il server-side apply e può aggiornare risorse esistenti..."
    ],
    "contexts": [
        ["# Ingress TLS\nPer abilitare TLS su Ingress, devi prima creare un Secret di tipo kubernetes.io/tls..."],
        ["# kubectl apply vs create\napply usa il patch merge e può modificare risorse esistenti, create fallisce se la risorsa esiste..."]
    ],
    "ground_truth": [
        "Un Ingress TLS richiede: 1) un Secret TLS (kubectl create secret tls) 2) la sezione tls: nell'Ingress spec",
        "apply = idempotent (crea o aggiorna), create = fallisce se già esiste"
    ]
}

dataset = Dataset.from_dict(ragas_data)
result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)

print(result)
# {'faithfulness': 0.87, 'answer_relevancy': 0.92, 'context_precision': 0.78, 'context_recall': 0.85}
```

### Interpretazione RAGAS

| Metrica | < 0.5 | 0.5-0.7 | > 0.7 | Azione se basso |
|---------|-------|---------|-------|-----------------|
| Faithfulness | Molto allucinante | Parzialmente grounded | Grounded | Migliorare il prompt per non inventare |
| Answer Relevancy | Risponde a domanda diversa | Parzialmente rilevante | Rilevante | Rivedere il retrieval e il prompt |
| Context Precision | Molto rumore nel context | Rumore moderato | Preciso | Ridurre k, aggiungere reranking |
| Context Recall | Context incompleto | Parzialmente completo | Completo | Aumentare k, migliorare chunking |

## 5. Evals in CI/CD

Integrare gli eval nel pipeline CI/CD permette di rilevare regressioni automaticamente.

```yaml
# .github/workflows/llm-eval.yml
name: LLM Evaluation

on:
  pull_request:
    paths:
      - 'prompts/**'
      - 'src/llm/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install anthropic pytest ragas

      - name: Run eval suite
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python run_evals.py --output results/eval_results.json

      - name: Check regression
        run: python check_regression.py --current results/eval_results.json --baseline results/baseline.json --threshold 0.05

      - name: Comment PR with results
        uses: actions/github-script@v7
        with:
          script: |
            const results = require('./results/eval_results.json');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## LLM Eval Results\n\nPass rate: ${results.pass_rate * 100:.1f}%\n...`
            });
```

```python
# check_regression.py
import json
import sys
import argparse

def check_regression(current_path: str, baseline_path: str, threshold: float) -> bool:
    """Fallisce se la pass_rate è scesa di più di threshold rispetto alla baseline."""
    with open(current_path) as f:
        current = json.load(f)
    with open(baseline_path) as f:
        baseline = json.load(f)

    regression = baseline["pass_rate"] - current["pass_rate"]
    if regression > threshold:
        print(f"REGRESSIONE RILEVATA: pass_rate scesa da {baseline['pass_rate']:.1%} a {current['pass_rate']:.1%} ({regression:.1%} di calo)")
        return False

    print(f"OK: pass_rate {current['pass_rate']:.1%} (baseline: {baseline['pass_rate']:.1%})")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--threshold", type=float, default=0.05)
    args = parser.parse_args()

    ok = check_regression(args.current, args.baseline, args.threshold)
    sys.exit(0 if ok else 1)
```

## 6. Framework di Valutazione

| Framework | Focus | Open Source | Hosted |
|-----------|-------|-------------|--------|
| **promptfoo** | Eval e testing prompt | Si | Si (cloud) |
| **Braintrust** | Eval + tracing + logging | Parziale | Si |
| **LangSmith** | LangChain ecosystem | No | Si |
| **Weave (W&B)** | MLOps + LLM evals | Parziale | Si |
| **RAGAS** | RAG evaluation | Si | No |
| **lm-eval** (EleutherAI) | Benchmark standardizzati | Si | No |

```bash
# promptfoo — il più semplice da iniziare
npm install -g promptfoo

# promptfooconfig.yaml
cat > promptfooconfig.yaml << 'EOF'
providers:
  - anthropic:claude-3-5-sonnet-20241022
  - anthropic:claude-3-5-haiku-20241022

prompts:
  - id: devops-reviewer
    raw: |
      System: {{system_prompt}}
      Human: {{user_message}}

tests:
  - vars:
      system_prompt: "Sei un senior DevOps engineer."
      user_message: "Come si debug un pod in CrashLoopBackOff?"
    assert:
      - type: contains
        value: kubectl logs
      - type: contains
        value: kubectl describe
      - type: not-contains
        value: non so
      - type: llm-rubric
        value: "La risposta include comandi kubectl specifici e spiega come interpretare l'output"
EOF

promptfoo eval
promptfoo view  # apre UI comparativa nel browser
```

## Best Practices

- **Inizia con 50-100 casi**: è sufficiente per avere segnale statistico per la maggior parte dei task. Aggiungi casi dove il modello fallisce.
- **Stratifica per difficoltà e categoria**: assicurati che l'eval set copra edge case, non solo i casi facili.
- **Separa eval set dal training set**: non usare mai dati di eval per il fine-tuning — invalida la valutazione.
- **Usa LLM-as-judge solo con modelli migliori del valutato**: non usare Haiku per giudicare Sonnet.
- **Traccia i costi**: ogni eval run costa token. Con suite grandi e modelli costosi, il costo si accumula.
- **Versiona l'eval set**: quando aggiungi o rimuovi test, registra la versione. I confronti tra versioni diverse dell'eval set non sono validi.
- **Monitora anche in produzione**: gli evals offline non catturano la distribuzione reale dell'input. Usa sampling + monitoring per valutare la qualità in produzione.

## Troubleshooting

### Scenario 1 — Pass rate scende improvvisamente in CI

**Sintomo:** La pipeline LLM eval fallisce con regressione > threshold anche senza modifiche ai prompt.

**Causa:** Il modello API può avere variazioni di comportamento tra versioni minori (es. `claude-3-5-sonnet-20241022` vs un aggiornamento silenzioso), oppure c'è non-determinismo con `temperature > 0`.

**Soluzione:** Fissa `temperature=0` per eval deterministici e aggiungi il checksum della versione modello al report.

```python
# Forza determinismo negli eval
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=2048,
    temperature=0,          # deterministico
    system=eval_case.input.get("system", ""),
    messages=[{"role": "user", "content": eval_case.input["user"]}]
)

# Salva la versione modello nel risultato per tracciabilità
result["model_version"] = response.model  # campo effettivo restituito dall'API
```

---

### Scenario 2 — LLM-as-Judge restituisce JSON malformato

**Sintomo:** `json.JSONDecodeError` frequente nel judge; il giudice aggiunge testo prima o dopo il JSON.

**Causa:** Il modello giudice inserisce preambolo testuale (`"Ecco la mia valutazione: {...}"`) o markdown code fence (` ```json`), rendendo il parsing diretto impossibile.

**Soluzione:** Usa un regex per estrarre il JSON o forza l'output con un tool/schema.

```python
import re

def extract_json(text: str) -> dict:
    """Estrae il primo oggetto JSON dal testo, ignorando preambolo e markdown."""
    # Rimuove code fence markdown
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Cerca il primo { ... } valido
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"Nessun JSON trovato nel testo: {text[:200]}")

# Oppure usa tool_choice per output strutturato garantito
response = client.messages.create(
    model=judge_model,
    max_tokens=512,
    tools=[{"name": "submit_evaluation", "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 5},
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
            "reasoning": {"type": "string"}
        },
        "required": ["score", "verdict", "reasoning"]
    }}],
    tool_choice={"type": "tool", "name": "submit_evaluation"},
    messages=[{"role": "user", "content": judge_prompt}]
)
result = response.content[0].input  # sempre JSON strutturato
```

---

### Scenario 3 — RAGAS restituisce NaN o score 0 su tutte le metriche

**Sintomo:** `evaluate()` ritorna `{'faithfulness': nan, 'answer_relevancy': nan, ...}`.

**Causa:** RAGAS usa internamente un LLM (OpenAI di default) per calcolare le metriche. Se la chiave API non è configurata o il modello non è accessibile, le chiamate falliscono silenziosamente.

**Soluzione:** Configura esplicitamente il modello RAGAS con le credenziali corrette.

```python
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic

# Usa Claude invece di OpenAI come modello RAGAS
claude_llm = LangchainLLMWrapper(ChatAnthropic(
    model="claude-3-5-haiku-20241022",  # modello economico per eval
    api_key="<ANTHROPIC_API_KEY>"
))

result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=claude_llm
)

# Debug: abilita logging per vedere le chiamate interne
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Scenario 4 — Benchmark lm-eval esauisce la memoria GPU

**Sintomo:** `CUDA out of memory` durante `lm_eval` con modelli 7B+ su GPU consumer.

**Causa:** Il batch size di default è troppo alto per la VRAM disponibile; i modelli grandi richiedono quantizzazione.

**Soluzione:** Riduci il batch size e abilita la quantizzazione a 4-bit.

```bash
# Riduci batch_size e abilita quantizzazione 4-bit
lm_eval \
    --model hf \
    --model_args "pretrained=meta-llama/Meta-Llama-3.1-8B-Instruct,load_in_4bit=True" \
    --tasks mmlu \
    --num_fewshot 5 \
    --batch_size 1 \
    --output_path results/mmlu

# Verifica VRAM disponibile prima di eseguire
nvidia-smi --query-gpu=memory.free,memory.total --format=csv

# Per modelli molto grandi: usa device_map=auto per distribuire su più GPU
lm_eval \
    --model hf \
    --model_args "pretrained=meta-llama/Meta-Llama-3.1-70B-Instruct,device_map=auto,load_in_8bit=True" \
    --tasks mmlu \
    --batch_size auto \
    --output_path results/mmlu-70b
```

---

## Riferimenti

- [RAGAS Documentation](https://docs.ragas.io/) — Framework valutazione RAG
- [promptfoo](https://promptfoo.dev/) — Testing e eval framework per prompt
- [lm-evaluation-harness (EleutherAI)](https://github.com/EleutherAI/lm-evaluation-harness) — Suite benchmark standardizzata
- [MMLU Paper (Hendrycks et al., 2020)](https://arxiv.org/abs/2009.03300) — Dataset MMLU originale
- [HumanEval (Chen et al., 2021)](https://arxiv.org/abs/2107.03374) — Benchmark coding
- [MT-Bench / FastChat (Zheng et al., 2023)](https://arxiv.org/abs/2306.05685) — Multi-turn chat evaluation
