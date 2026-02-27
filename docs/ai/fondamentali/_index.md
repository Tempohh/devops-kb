---
title: "Fondamentali AI & Machine Learning"
slug: fondamentali-ai
category: ai
tags: [ai, machine-learning, deep-learning, llm, neural-networks]
search_keywords: [intelligenza artificiale, artificial intelligence, ML, DL, large language model, reti neurali, supervised learning, unsupervised learning, reinforcement learning, foundation model, AI fondamentali]
parent: ai/_index
related: [ai/modelli/_index, ai/training/fine-tuning, ai/tokens-context/_index]
official_docs: https://developers.google.com/machine-learning/crash-course
status: complete
difficulty: beginner
last_updated: 2026-02-27
---

# Fondamentali AI & Machine Learning

## Panoramica

Questa sezione copre i fondamentali teorici e pratici dell'intelligenza artificiale applicata al contesto DevOps e allo sviluppo software moderno. Il campo AI si articola in una progressione di paradigmi sempre più potenti: dal Machine Learning classico al Deep Learning, fino agli LLM (Large Language Models) e ai sistemi agentici autonomi. Comprendere questa progressione permette di scegliere lo strumento giusto per ogni problema, evitando sia l'over-engineering che l'under-engineering.

L'AI non è una tecnologia monolitica: ogni livello della stack ha i propri casi d'uso, costi di addestramento, requisiti infrastrutturali e trade-off. Un ingegnere DevOps moderno deve sapere quando usare un semplice classificatore scikit-learn, quando orchestrare un sistema RAG, e quando un LLM come Claude è la scelta appropriata.

## Progressione dei Paradigmi AI

La tabella seguente mostra l'evoluzione storica e concettuale del campo, con le implicazioni pratiche per ogni livello.

| Livello | Paradigma | Esempio | Dati Necessari | Compute | Caso d'Uso Tipico |
|---------|-----------|---------|----------------|---------|-------------------|
| 1 | **Machine Learning Classico** | Random Forest, SVM, XGBoost | Tabellare, strutturato | CPU — minuti/ore | Anomaly detection, classificazione log, previsione costi cloud |
| 2 | **Deep Learning** | CNN, RNN, MLP | Immagini, sequenze, testo | GPU — ore/giorni | Classificazione immagini, NLP specializzato, time series |
| 3 | **Foundation Model / LLM** | GPT-4, Claude, Llama 3 | Miliardi di documenti (pre-training) | GPU cluster — mesi | Generazione codice, analisi testo, chatbot, RAG |
| 4 | **Agenti AI** | Claude Code, AutoGen | Tool access + LLM | LLM API + infra | Automazione workflow, incident analysis, code agent |

### Da Machine Learning a LLM: le differenze chiave

```
ML Classico
 ├── Feature engineering manuale
 ├── Training su task specifico
 ├── Inferenza veloce (ms)
 └── Interpretabilità alta

Deep Learning
 ├── Feature learning automatico
 ├── Transfer learning possibile
 ├── Training computazionalmente intenso
 └── Interpretabilità ridotta (black box)

LLM
 ├── Comprensione linguaggio naturale
 ├── Reasoning e generazione
 ├── Few-shot / zero-shot learning
 ├── Context window come "memoria temporanea"
 └── Costo per token (API) o infra GPU pesante

Agenti AI
 ├── LLM + tool use (filesystem, API, database)
 ├── Planning multi-step
 ├── Memoria persistente (opzionale)
 └── Loop autonomo con feedback
```

## Concetti Trasversali

### Cos'è il Training

Il training è il processo con cui un modello apprende dai dati. Indipendentemente dal paradigma, il processo generale è:

1. **Inizializzazione**: parametri (pesi) inizializzati casualmente o con transfer learning
2. **Forward pass**: i dati passano attraverso il modello e producono una predizione
3. **Loss calculation**: si misura quanto la predizione è sbagliata rispetto alla verità (label)
4. **Backpropagation**: il gradiente della loss viene propagato indietro attraverso il modello
5. **Gradient descent**: i parametri vengono aggiornati nella direzione che minimizza la loss
6. **Iterazione**: i passi 2-5 si ripetono per molti epoch fino a convergenza

### Cos'è l'Inferenza

L'inferenza è l'uso del modello già addestrato per produrre predizioni su nuovi dati. L'inferenza è tipicamente molto più veloce del training. Per gli LLM, l'inferenza è il processo di generazione token-per-token.

### Train / Validation / Test Split

```
Dataset totale
├── Training set (60-80%): usato per aggiornare i pesi
├── Validation set (10-20%): usato per monitorare overfitting e tuning
└── Test set (10-20%): usato UNA SOLA VOLTA per valutazione finale
```

!!! warning "Data leakage"
    Il test set non deve MAI essere visto durante il training o il validation. Qualsiasi preprocessing (normalizzazione, encoding) deve essere fit sul training set e applicato agli altri set.

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Machine Learning**

    ---

    Paradigmi supervised, unsupervised, reinforcement. Algoritmi classici, training loop, overfitting/underfitting. Librerie Python.

    [:octicons-arrow-right-24: Machine Learning](machine-learning.md)

-   **Deep Learning**

    ---

    Reti neurali, CNN, RNN/LSTM, Transformer. PyTorch training loop completo. GPU training e mixed precision.

    [:octicons-arrow-right-24: Deep Learning](deep-learning.md)

-   **LLM — Architettura**

    ---

    Architettura Transformer, attention mechanism, pre-training e tokenizzazione. Come funziona un LLM dall'interno.

    [:octicons-arrow-right-24: Architettura LLM](../modelli/_index.md)

</div>

## Riferimenti

- [Google ML Crash Course](https://developers.google.com/machine-learning/crash-course) — Introduzione pratica al ML
- [fast.ai — Practical Deep Learning](https://course.fast.ai/) — Corso deep learning top-down
- [Andrej Karpathy — Neural Networks: Zero to Hero](https://karpathy.ai/zero-to-hero.html) — Dal perceptron agli LLM
- [Stanford CS229 — Machine Learning](https://cs229.stanford.edu/) — Fondamenta matematiche
- [Attention Is All You Need (Vaswani et al., 2017)](https://arxiv.org/abs/1706.03762) — Il paper che ha introdotto il Transformer
