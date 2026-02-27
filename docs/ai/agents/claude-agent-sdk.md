---
title: "Claude Agent SDK e Claude Code"
slug: claude-agent-sdk
category: ai
tags: [claude-code, agent-sdk, mcp, model-context-protocol, claude-agents]
search_keywords: [Claude Code, agente AI coding, Claude Agent SDK, MCP server, Model Context Protocol, CLAUDE.md, tool use Claude, subagent, Task tool, hook Claude, permessi Claude Code, settings.json Claude, anthropic SDK Python, agente custom Claude]
parent: ai/agents/_index
related: [ai/agents/_index, ai/agents/frameworks, ai/sviluppo/prompt-engineering, ai/mlops/pipeline-ml]
official_docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Claude Agent SDK e Claude Code

## Panoramica

Claude Code è un agente AI sviluppato da Anthropic che opera direttamente nel filesystem, esegue comandi shell, legge e scrive codice, e naviga il web. È accessibile come CLI (`claude`) e rappresenta il modo più diretto per usare Claude come agente di sviluppo. Parallelamente, l'**Anthropic Agent SDK** (API Python/TypeScript) permette di costruire agenti custom che sfruttano la stessa potenza di Claude con tool personalizzati, workflow orchestrati e integrazione in sistemi esistenti.

Comprendere Claude Code e l'SDK è essenziale per due ragioni complementari: prima, per usare efficacemente Claude Code come strumento di sviluppo quotidiano (configurazione, CLAUDE.md, permessi); seconda, per costruire agenti custom per automazione DevOps (incident analysis, code review, generazione IaC).

## 1. Claude Code — L'Agente CLI

### Installazione e Avvio

```bash
# Installazione
npm install -g @anthropic-ai/claude-code

# Configurazione chiave API
export ANTHROPIC_API_KEY="sk-ant-..."

# Avvio nella directory di progetto
cd /path/to/project
claude

# Modalità non-interattiva (scripting)
claude --print "Spiega l'architettura di questo progetto"

# Con permessi specifici
claude --allowedTools "Read,Write,Bash(git:*)"
```

### Tool Disponibili in Claude Code

| Tool | Descrizione | Sicurezza |
|------|-------------|---------|
| **Read** | Legge file dal filesystem | Safe — read-only |
| **Write** | Scrive/sovrascrive file | Modificante — richiede conferma |
| **Edit** | Modifica sezioni di file (più preciso di Write) | Modificante |
| **Bash** | Esegue comandi shell | Potenzialmente distruttivo |
| **Glob** | Cerca file per pattern | Safe |
| **Grep** | Cerca contenuto nei file (ripgrep) | Safe |
| **WebFetch** | Fetcha contenuto da URL | Network |
| **Task** | Lancia sub-agente Claude | Costoso (nuova sessione) |
| **TodoWrite** | Gestisce lista task della sessione | Safe |

### CLAUDE.md — Il File di Istruzioni

Il file `CLAUDE.md` nella root del progetto (o in `~/.claude/CLAUDE.md` per configurazione globale) fornisce istruzioni persistenti a Claude Code per ogni sessione. È il meccanismo principale per "programmarlo" per il tuo progetto specifico.

```markdown
# CLAUDE.md — MyProject

## Stack Tecnico
- Backend: Python 3.11 + FastAPI
- Database: PostgreSQL 16 con SQLAlchemy ORM
- Infrastruttura: Kubernetes su EKS, Terraform
- CI/CD: GitHub Actions

## Convenzioni di Codice
- Stile: black + isort + ruff
- Test: pytest, coverage minima 80%
- Commits: Conventional Commits (feat:, fix:, chore:)
- Branch: feature/TICKET-ID-descrizione

## Comandi Principali
- `make test` — esegui test suite completa
- `make lint` — linting e formatting
- `make migrate` — applica migrazioni Alembic
- `kubectl apply -f k8s/` — deploy su staging

## Architettura
[Descrizione architettura, componenti, naming convention]

## Regole Operative
- Non modificare mai i file di migrazione esistenti
- Ogni PR richiede test per i casi edge
- I secret vanno in AWS Secrets Manager, MAI in codice o variabili env
```

### Configurazione Sicurezza (settings.json)

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Write",
      "Edit",
      "Bash(git:*)",
      "Bash(kubectl get:*)",
      "Bash(kubectl describe:*)",
      "Bash(docker build:*)",
      "Glob",
      "Grep",
      "WebFetch"
    ],
    "deny": [
      "Bash(kubectl delete:*)",
      "Bash(terraform destroy:*)",
      "Bash(rm -rf:*)"
    ]
  }
}
```

Il file `settings.json` si trova in `.claude/settings.json` (per-progetto) o `~/.claude/settings.json` (globale). I permessi definiti in `deny` hanno priorità assoluta.

### Hook System

Gli hook permettono di intercettare le azioni di Claude Code prima e dopo l'esecuzione:

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/validate_command.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/log_file_change.py"
          }
        ]
      }
    ]
  }
}
```

```python
# validate_command.py — hook PreToolUse per Bash
import sys
import json

# Input da stdin: JSON con tool_name e tool_input
hook_input = json.loads(sys.stdin.read())
command = hook_input.get("tool_input", {}).get("command", "")

BLOCKED_PATTERNS = ["rm -rf /", "DROP TABLE", "kubectl delete namespace"]

for pattern in BLOCKED_PATTERNS:
    if pattern in command:
        # Exit code 1 = blocca l'esecuzione
        # Exit code 2 = blocca e notifica Claude
        print(f"BLOCCATO: comando pericoloso rilevato: {pattern}", file=sys.stderr)
        sys.exit(2)

sys.exit(0)  # OK, procedi
```

## 2. Tool Use via Anthropic Python SDK

Il tool use è il meccanismo fondamentale per costruire agenti custom. Claude decide quale tool chiamare, il codice esegue il tool, il risultato viene restituito a Claude nel loop.

```python
import anthropic
import subprocess
import json
from pathlib import Path

client = anthropic.Anthropic()

# Definizione dei tool
tools = [
    {
        "name": "read_file",
        "description": "Legge il contenuto di un file dal filesystem locale",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path assoluto o relativo al file"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "execute_command",
        "description": "Esegue un comando shell e restituisce stdout, stderr, e exit code",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Comando shell da eseguire"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in secondi (default 30)",
                    "default": 30
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "write_file",
        "description": "Scrive contenuto in un file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    }
]

# Implementazione dei tool
def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "read_file":
        path = Path(tool_input["path"])
        if not path.exists():
            return f"Errore: file non trovato: {path}"
        return path.read_text(encoding="utf-8")

    elif tool_name == "execute_command":
        command = tool_input["command"]
        timeout = tool_input.get("timeout", 30)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return json.dumps({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            })
        except subprocess.TimeoutExpired:
            return json.dumps({"error": f"Timeout dopo {timeout}s", "exit_code": -1})

    elif tool_name == "write_file":
        path = Path(tool_input["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tool_input["content"], encoding="utf-8")
        return f"File scritto: {path} ({len(tool_input['content'])} caratteri)"

    return f"Tool sconosciuto: {tool_name}"

# Agent loop
def run_agent(task: str, system_prompt: str, max_steps: int = 20) -> str:
    messages = [{"role": "user", "content": task}]

    for step in range(max_steps):
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        # Aggiungi risposta alla storia
        messages.append({"role": "assistant", "content": response.content})

        # Controlla stop reason
        if response.stop_reason == "end_turn":
            # Nessun tool call — l'agente ha finito
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[-1].text if text_blocks else "Task completato"

        if response.stop_reason == "tool_use":
            # Esegui i tool richiesti
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Step {step+1}] Tool: {block.name}({block.input})")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Aggiungi risultati tool alla storia
            messages.append({"role": "user", "content": tool_results})

    return "Raggiunto il massimo numero di step"

# Utilizzo
result = run_agent(
    task="Analizza il Dockerfile in ./Dockerfile e suggerisci 3 ottimizzazioni per la sicurezza",
    system_prompt="Sei un esperto di sicurezza container Docker. Analizza i file e fornisci feedback concreti e actionable."
)
print(result)
```

## 3. Sub-agenti con il Task Tool

Claude Code supporta la creazione di **sub-agenti** tramite il `Task` tool, permettendo parallelizzazione e specializzazione:

```python
# Nella definizione dei tool per un orchestrator agent
task_tool = {
    "name": "spawn_subagent",
    "description": """Lancia un sub-agente Claude per eseguire un sotto-task in modo autonomo.
    Il sub-agente ha accesso agli stessi tool dell'agente principale.
    Usare per task parallelizzabili o task che richiedono isolamento.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "Descrizione completa del task da eseguire"
            },
            "working_directory": {
                "type": "string",
                "description": "Directory di lavoro per il sub-agente"
            }
        },
        "required": ["task_description"]
    }
}
```

Esempio di orchestration multi-agente:

```python
# Orchestrator: analizza una PR con più sub-agenti in parallelo
orchestrator_prompt = """
Hai ricevuto una PR da analizzare. Spawna 3 sub-agenti in parallelo:
1. Security Agent: analizza vulnerabilità sicurezza, OWASP Top 10
2. Performance Agent: identifica problemi di performance, complessità algoritmica
3. Style Agent: verifica conformità alle coding guidelines del progetto

Poi integra i risultati in un report finale.
"""
```

## 4. MCP — Model Context Protocol

Il Model Context Protocol (MCP) è uno standard aperto sviluppato da Anthropic per la comunicazione tra LLM (client) e tool/dati (server). Claude Code è un client MCP nativo.

### Architettura MCP

```
┌─────────────────┐       ┌─────────────────┐
│   Claude Code   │       │   MCP Server    │
│   (MCP Client)  │──────▶│ (Tool Provider) │
│                 │ JSON  │                 │
│  ·Tool calls    │──────▶│ ·Jira API       │
│  ·Resource reads│       │ ·Prometheus API │
│  ·Prompts       │◀──────│ ·Git operations │
└─────────────────┘       └─────────────────┘

Protocollo: JSON-RPC 2.0 su stdio o HTTP/SSE
```

### Configurazione MCP in Claude Code

```json
// ~/.claude/claude_desktop_config.json (per Claude Desktop)
// o .claude/mcp.json (per progetto)
{
  "mcpServers": {
    "jira": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-jira"],
      "env": {
        "JIRA_URL": "https://mycompany.atlassian.net",
        "JIRA_TOKEN": "${JIRA_API_TOKEN}"
      }
    },
    "prometheus": {
      "command": "python",
      "args": ["-m", "mcp_prometheus"],
      "env": {
        "PROMETHEUS_URL": "http://prometheus.monitoring.svc:9090"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
    }
  }
}
```

### Costruire un MCP Server Custom

```python
# mcp_prometheus_server.py — MCP server che espone query Prometheus
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import httpx

app = Server("prometheus-mcp")
PROMETHEUS_URL = "http://localhost:9090"

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="query_prometheus",
            description="Esegue una query PromQL su Prometheus e restituisce i risultati",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query PromQL"
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Range temporale: '5m', '1h', '24h' (default: 5m)"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="list_alerts",
            description="Lista tutti gli alert attivi in Prometheus",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    async with httpx.AsyncClient() as client:
        if name == "query_prometheus":
            query = arguments["query"]
            time_range = arguments.get("time_range", "5m")
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query}
            )
            data = response.json()
            return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "list_alerts":
            response = await client.get(f"{PROMETHEUS_URL}/api/v1/alerts")
            alerts = response.json()
            return [types.TextContent(type="text", text=json.dumps(alerts, indent=2))]

    return [types.TextContent(type="text", text="Tool non trovato")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

```bash
# Installazione dipendenze
pip install mcp httpx

# Test del server
python mcp_prometheus_server.py
```

## 5. Esempio Completo — Agente Analisi Incidenti

```python
"""
Agente di analisi incidenti che:
1. Riceve un alert Prometheus
2. Raccoglie log da Loki
3. Analizza le metriche correlate
4. Genera un runbook di risposta
5. Crea ticket Jira
"""

import anthropic
import httpx
import json
from datetime import datetime, timedelta

client = anthropic.Anthropic()

# Tool definitions per l'agente
incident_tools = [
    {
        "name": "query_prometheus",
        "description": "Esegue query PromQL per ottenere metriche",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "start": {"type": "string", "description": "ISO timestamp"},
                "end": {"type": "string", "description": "ISO timestamp"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_loki",
        "description": "Cerca log in Loki con LogQL",
        "input_schema": {
            "type": "object",
            "properties": {
                "logql": {"type": "string", "description": "Query LogQL"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["logql"]
        }
    },
    {
        "name": "get_k8s_events",
        "description": "Ottieni gli eventi Kubernetes recenti per un namespace",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "since_minutes": {"type": "integer", "default": 30}
            },
            "required": ["namespace"]
        }
    },
    {
        "name": "create_jira_ticket",
        "description": "Crea un ticket Jira per l'incidente",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "severity": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "assignee": {"type": "string"}
            },
            "required": ["title", "description", "severity"]
        }
    }
]

INCIDENT_SYSTEM_PROMPT = """
Sei un SRE senior specializzato in analisi di incidenti. Quando ricevi un alert:

1. RACCOGLI DATI: usa i tool per raccogliere metriche, log ed eventi K8s correlati
2. ANALIZZA ROOT CAUSE: identifica la causa radice, non i sintomi
3. VALUTA IMPATTO: stima l'impatto sugli utenti e il perimetro dell'incidente
4. SUGGERISCI REMEDIATION: passi concreti e ordinati per risolvere
5. CREA TICKET: documenta tutto in un ticket Jira strutturato

Il tuo output finale deve essere un JSON strutturato con:
- root_cause: causa radice identificata
- impact: impatto stimato
- remediation_steps: lista ordinata di passi
- jira_ticket_id: ID del ticket creato
"""

async def analyze_incident(alert: dict) -> dict:
    """
    Analizza un incidente dato un alert Prometheus.

    Args:
        alert: dict con alertname, labels, annotations, startsAt

    Returns:
        dict con analisi completa
    """
    task = f"""
Analizza questo alert Prometheus:

Alert: {alert['alertname']}
Severity: {alert['labels'].get('severity', 'unknown')}
Namespace: {alert['labels'].get('namespace', 'unknown')}
Service: {alert['labels'].get('service', 'unknown')}
Summary: {alert['annotations'].get('summary', '')}
Description: {alert['annotations'].get('description', '')}
Started: {alert['startsAt']}

Inizia raccogliendo dati, poi analizza e crea il ticket.
"""

    messages = [{"role": "user", "content": task}]
    result = {}

    for step in range(15):  # max 15 step
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=INCIDENT_SYSTEM_PROMPT,
            tools=incident_tools,
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Estrai il JSON dalla risposta finale
            for block in response.content:
                if hasattr(block, 'text'):
                    try:
                        result = json.loads(block.text)
                    except json.JSONDecodeError:
                        result = {"analysis": block.text}
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_result = await execute_incident_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    })
            messages.append({"role": "user", "content": tool_results})

    return result
```

## Best Practices

- **Granularità dei tool**: tool troppo generici (es. `execute_any_command`) sono pericolosi. Tool specifici (es. `kubectl_get_pods`, `query_prometheus`) sono più sicuri e permettono permessi più granulari.
- **Error handling nei tool**: i tool devono restituire errori chiari e strutturati (JSON con `error` field), non eccezioni non gestite. L'agente deve poter ragionare sull'errore.
- **Timeout obbligatori**: ogni chiamata a tool esterni deve avere un timeout esplicito. Un tool che non risponde blocca l'intero agente.
- **Logging di ogni tool call**: logga input e output di ogni tool call per debugging e audit. Gli agenti possono fallire in modi non intuitivi.
- **Limita i passi del loop**: imposta sempre un `max_steps` per evitare loop infiniti costosi. 10-20 step è sufficiente per la maggior parte dei task.
- **CLAUDE.md per ogni progetto**: il file CLAUDE.md è il modo più efficiente per contestualizzare Claude Code al tuo progetto. Mantienilo aggiornato.
- **Test su task semplici prima**: valida l'agente con task controllati e incrementa la complessità gradualmente.

## Riferimenti

- [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — Guida ufficiale completa
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — Spec e server MCP ufficiali
- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code) — Guida Claude Code
- [anthropic-sdk-python](https://github.com/anthropic-ai/anthropic-sdk-python) — SDK Python ufficiale
- [MCP Servers Repository](https://github.com/modelcontextprotocol/servers) — Server MCP pronti all'uso
