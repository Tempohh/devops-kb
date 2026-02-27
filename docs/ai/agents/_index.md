---
title: "Agenti AI"
slug: agents-ai
category: ai
tags: [agents, agentic-ai, tool-use, autonomous]
search_keywords: [agenti AI, AI agents, agente autonomo, tool use, function calling, agentic workflow, LLM agent, multi-agent, planning LLM, memory agent, ReAct pattern, chain of thought agent, Claude Code, AutoGen, LangChain agent, CrewAI]
parent: ai/_index
related: [ai/agenti/claude-agent-sdk, ai/agenti/frameworks, ai/sviluppo/prompt-engineering, ai/sviluppo/rag]
official_docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# Agenti AI

## Panoramica

Un agente AI è un sistema che usa un LLM non solo per rispondere a una singola domanda, ma per **pianificare e eseguire sequenze di azioni** per raggiungere un obiettivo. L'LLM funge da "cervello" che decide cosa fare, mentre gli strumenti (tool) forniscono la capacità di agire sul mondo reale: leggere file, eseguire comandi, chiamare API, cercare nel web, scrivere codice.

La distinzione tra un chatbot e un agente è la **capacità d'azione nel loop**. Un chatbot risponde. Un agente legge un file di log, identifica un'anomalia, query un database di metriche, chiama l'API di monitoring, apre un ticket su Jira, e invia una notifica Slack — il tutto in autonomia, con la sola indicazione dell'obiettivo finale. In ambito DevOps, questo paradigma apre scenari di automazione prima impossibili senza codice specializzato per ogni caso d'uso.

## Spectrum: da Chatbot ad Agente Autonomo

```
Chatbot Semplice
  │  LLM + prompt → risposta
  │  Nessun tool, nessun loop
  ↓

LLM Aumentato (Augmented LLM)
  │  LLM + tool use (singola chiamata)
  │  Esempio: chiede il meteo via API, risponde
  ↓

Agente (Agent Loop)
  │  LLM + tool loop: osserva → pensa → agisce → osserva → ...
  │  Esempio: ClaudeCode che legge, modifica, testa il codice
  ↓

Agente Multi-Step con Planning
  │  LLM pianifica sub-task, li esegue in sequenza
  │  Verifica il risultato, corregge, itera
  ↓

Sistema Multi-Agente
  │  Più agenti specializzati collaborano
  │  Agente ricercatore, agente esecutore, agente reviewer
  ↓

Agente Autonomo (Agentic Loop Lungo)
     Obiettivo di alto livello → settimane di esecuzione autonoma
     Esempio: gestione automatica infrastruttura, trading bot
```

## Componenti di un Agente

Ogni agente è composto da quattro elementi fondamentali:

### 1. LLM (Il Cervello)

Il modello decide cosa fare a ogni step. Riceve lo stato corrente (obiettivo + risultati precedenti + osservazioni dei tool) e produce:
- Un'azione (chiamata a un tool)
- Oppure la risposta finale (se l'obiettivo è raggiunto)

La qualità del reasoning del modello determina la qualità dell'agente. Modelli frontier (Claude 3.5 Sonnet, GPT-4o) sono molto più affidabili come agenti rispetto a modelli più piccoli.

### 2. Tools (Le Mani)

I tool definiscono cosa l'agente può fare. Ogni tool ha:
- Nome e descrizione (l'LLM usa queste per decidere quale tool usare)
- Schema parametri (JSON Schema)
- Implementazione (funzione Python, API call, ecc.)

```python
# Esempio tool per Claude
tools = [
    {
        "name": "read_file",
        "description": "Legge il contenuto di un file dal filesystem",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path assoluto del file da leggere"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "execute_command",
        "description": "Esegue un comando shell e restituisce stdout/stderr",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 30}
            },
            "required": ["command"]
        }
    }
]
```

### 3. Memory (La Memoria)

Gli agenti possono avere diversi tipi di memoria:

| Tipo | Descrizione | Implementazione |
|------|-------------|-----------------|
| **In-context** | Tutto ciò che è nella context window corrente | Parte del prompt |
| **Episodica** | Risultati delle azioni precedenti nel loop | Conversation history |
| **Semantica** | Knowledge base consultabile | RAG + vector DB |
| **Persistente** | Stato salvato tra sessioni | Database, file |

### 4. Planning (La Strategia)

Il planning è la capacità dell'agente di scomporre un obiettivo complesso in sotto-task eseguibili. Può essere:

- **Implicito (ReAct)**: l'agente ragiona e agisce alternativamente — ogni risposta include un reasoning step e una action
- **Esplicito (Plan-and-Execute)**: l'agente genera prima un piano completo, poi lo esegue
- **Gerarchico**: un "planner agent" coordina più "executor agents"

## Pattern ReAct

ReAct (Reasoning + Acting) è il pattern di base per agenti. L'agente alterna pensiero (reasoning) e azione (tool call):

```
Obiettivo: "Verifica se l'applicazione myapp-production è healthy e, se no, riavvila"

Step 1:
  Thought: Devo prima verificare lo stato dei pod
  Action: execute_command(command="kubectl get pods -n production -l app=myapp")
  Observation: myapp-7d8f9b-xxx  0/1  CrashLoopBackOff  5  10m

Step 2:
  Thought: Il pod è in CrashLoopBackOff. Devo vedere i log per capire il problema
  Action: execute_command(command="kubectl logs myapp-7d8f9b-xxx -n production --tail=50")
  Observation: ERROR: Connection refused to database on port 5432

Step 3:
  Thought: C'è un problema di connessione al database. Verifico se postgres è up
  Action: execute_command(command="kubectl get pods -n production -l app=postgres")
  Observation: postgres-0  0/1  Pending  0  15m

Step 4:
  Thought: Postgres è in Pending. Prima risolvo il database
  Action: execute_command(command="kubectl describe pod postgres-0 -n production")
  Observation: Warning  FailedScheduling: 0/3 nodes available: insufficient memory

Step 5:
  Thought: Nodo senza memoria. Devo controllare i nodi e decidere se fare scale-out
  Action: [...]

Final Answer: Il problema è una carenza di memoria sui nodi. Postgres non può schedulare,
              causando il crash di myapp. Consiglio: kubectl scale node group o ridurre requests.
              Ho creato il ticket INFRA-1234 con il dettaglio.
```

## Casi d'Uso DevOps

### Code Agent

Legge codebase, capisce il problema, scrive il fix, esegue i test, propone la PR.

```
Tool: read_file, write_file, execute_bash, create_pr, run_tests
LLM: Claude 3.5 Sonnet (miglior SWE-bench score)
```

### Infra Agent

Analizza lo stato dell'infrastruttura, propone o applica modifiche (IaC), monitora il risultato.

```
Tool: kubectl, terraform, aws_cli, describe_resource, apply_manifest
LLM: Claude 3.5 Sonnet + CLAUDE.md con naming convention e policy
```

### Incident Analysis Agent

Viene attivato da un alert PagerDuty, raccoglie contesto (log, metriche, eventi), genera un runbook di risposta, crea il ticket, notifica il team.

```
Tool: query_loki_logs, query_prometheus, get_k8s_events, create_jira_ticket, send_slack_message
LLM: Claude 3.5 Sonnet per reasoning, Haiku per classificazione veloce
```

### Doc Generation Agent

Legge il codice, le API spec, i ticket recenti, genera documentazione aggiornata.

```
Tool: read_codebase, read_openapi_spec, list_git_commits, write_markdown
LLM: Claude per qualità del testo generato
```

## Argomenti di Questa Sezione

<div class="grid cards" markdown>

-   **Claude Agent SDK e Claude Code**

    ---

    Claude Code come agente di sviluppo. Agent SDK Python per agenti custom. MCP (Model Context Protocol). Hooks e permessi.

    [:octicons-arrow-right-24: Claude Agent SDK](claude-agent-sdk.md)

-   **Framework Agentici**

    ---

    LangChain, LlamaIndex, AutoGen, CrewAI, LangGraph. Confronto e quando usare ogni framework.

    [:octicons-arrow-right-24: Frameworks](frameworks.md)

</div>

## Riferimenti

- [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — Guida ufficiale tool use con Claude
- [ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., 2022)](https://arxiv.org/abs/2210.03629) — Paper originale ReAct
- [Anthropic Agentic AI Research](https://www.anthropic.com/research) — Ricerca su sicurezza e capacità agentica
- [Building Effective Agents (Anthropic, 2024)](https://www.anthropic.com/research/building-effective-agents) — Best practices per agenti
