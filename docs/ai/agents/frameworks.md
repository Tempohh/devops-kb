---
title: "Framework Agentici — LangChain, LlamaIndex, AutoGen"
slug: frameworks
category: ai
tags: [langchain, llamaindex, autogen, crewai, langgraph, frameworks]
search_keywords: [LangChain, LlamaIndex, AutoGen, CrewAI, LangGraph, framework agentici, orchestrazione LLM, LCEL, LangChain Expression Language, multi-agent framework, agentic workflow, RAG framework, chain LangChain]
parent: ai/agents/_index
related: [ai/agents/_index, ai/agenti/claude-agent-sdk, ai/sviluppo/rag, ai/sviluppo/prompt-engineering]
official_docs: https://python.langchain.com/docs/
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# Framework Agentici — LangChain, LlamaIndex, AutoGen

## Panoramica

L'ecosistema dei framework agentici è cresciuto rapidamente con l'esplosione degli LLM. I framework promettono di astrarre la complessità dell'orchestrazione, delle integrazioni, e del tool use — ma spesso aggiungono layer di complessità, indirection, e debugging difficile. Questo documento copre i principali framework con esempi reali, pro/contro onesti, e una guida su quando usarli vs implementare da zero.

La regola empirica: per applicazioni semplici (RAG lineare, chatbot con pochi tool), il codice custom con l'SDK del provider è quasi sempre più manutenibile. I framework diventano utili per orchestrare workflow complessi, multi-agent, o quando hai bisogno di molte integrazioni precostruite.

## 1. LangChain

LangChain è il framework più popolare per applicazioni LLM, con un ecosistema enorme di integrazioni (100+ vector store, 50+ LLM provider, decine di tool). La versione moderna usa **LCEL (LangChain Expression Language)** per definire chain composabili.

### LCEL — LangChain Expression Language

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# LLM
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)

# Chain semplice: prompt | llm | parser
prompt = ChatPromptTemplate.from_messages([
    ("system", "Sei un esperto DevOps. Rispondi in italiano."),
    ("human", "{question}")
])

chain = prompt | llm | StrOutputParser()

# Invocazione
result = chain.invoke({"question": "Come funziona il rolling update in Kubernetes?"})
print(result)

# Streaming
for chunk in chain.stream({"question": "Spiega Helm in 5 punti"}):
    print(chunk, end="", flush=True)

# Batch
results = chain.batch([
    {"question": "Cos'è un Service Mesh?"},
    {"question": "Differenza tra StatefulSet e Deployment"},
])
```

### RAG Chain con LangChain

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader

# Carica documenti
loader = DirectoryLoader("./docs", glob="**/*.md")
documents = loader.load()

# Chunking
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(documents)

# Vector store
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# RAG chain con LCEL
from langchain_core.runnables import RunnableParallel

rag_prompt = ChatPromptTemplate.from_template("""
Rispondi alla domanda basandoti SOLO sui seguenti documenti:

{context}

Domanda: {question}

Se la risposta non è nei documenti, dì esplicitamente "Non trovo questa informazione nella documentazione."
""")

def format_docs(docs):
    return "\n\n---\n\n".join(f"Fonte: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}" for doc in docs)

rag_chain = (
    RunnableParallel(context=retriever | format_docs, question=RunnablePassthrough())
    | rag_prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("Come si configura un Ingress con TLS?")
```

### LangChain Agents

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool

@tool
def get_kubernetes_pod_status(namespace: str, pod_name: str) -> str:
    """Ottieni lo status di un pod Kubernetes."""
    import subprocess
    result = subprocess.run(
        f"kubectl get pod {pod_name} -n {namespace} -o json",
        shell=True, capture_output=True, text=True
    )
    return result.stdout or result.stderr

@tool
def query_prometheus(promql: str) -> str:
    """Esegui una query PromQL su Prometheus."""
    import httpx
    response = httpx.get("http://localhost:9090/api/v1/query", params={"query": promql})
    return response.text

tools = [get_kubernetes_pod_status, query_prometheus]

# Crea agent con tool calling (più stabile di ReAct per LangChain)
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)

result = agent_executor.invoke({
    "input": "Verifica lo status dell'applicazione myapp nel namespace production"
})
print(result["output"])
```

**Pro LangChain:**
- Ecosistema enorme — quasi ogni integrazione esiste già
- LCEL è elegante per chain semplici e medie
- Buona documentazione ed esempi

**Contro LangChain:**
- Spesso over-engineered per task semplici
- Debugging difficile per chain complesse (molti layer di astrazione)
- API cambia frequentemente (LangChain 0.x → 0.1 → 0.2 → 0.3 = breaking changes)
- Overhead significativo (import lento, molte dipendenze)

!!! warning "Versioning LangChain"
    LangChain ha una storia di breaking changes tra versioni minori. Specifica sempre la versione esatta in `requirements.txt`. Considera se la dependency vale il rischio per la tua applicazione.

## 2. LlamaIndex

LlamaIndex è focalizzato su RAG e data indexing. Dove LangChain è generalista, LlamaIndex eccelle nel connettere LLM a sorgenti dati strutturate e non strutturate.

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.anthropic import Anthropic
from llama_index.embeddings.openai import OpenAIEmbedding

# Configura LLM e embeddings
Settings.llm = Anthropic(model="claude-3-5-sonnet-20241022")
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# Carica e indicizza documenti
documents = SimpleDirectoryReader("./docs").load_data()
index = VectorStoreIndex.from_documents(documents)

# Query engine semplice
query_engine = index.as_query_engine(similarity_top_k=5)
response = query_engine.query("Quali sono le best practice per la sicurezza Kubernetes?")
print(response)

# Accedi ai source nodes (per citazioni)
for node in response.source_nodes:
    print(f"- {node.metadata.get('file_name')}: score {node.score:.3f}")
```

### SubQuestion Query Engine

```python
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.tools import QueryEngineTool

# Crea query engine per diverse sezioni della KB
k8s_engine = VectorStoreIndex.from_documents(k8s_docs).as_query_engine()
security_engine = VectorStoreIndex.from_documents(security_docs).as_query_engine()

tools = [
    QueryEngineTool.from_defaults(k8s_engine, name="kubernetes", description="Documentazione Kubernetes"),
    QueryEngineTool.from_defaults(security_engine, name="security", description="Documentazione Security")
]

# Decompone domande complesse in sub-domande
sub_question_engine = SubQuestionQueryEngine.from_defaults(query_engine_tools=tools)
response = sub_question_engine.query(
    "Come si implementa un NetworkPolicy Kubernetes per limitare il traffico ai soli pod autenticati?"
)
```

**Pro LlamaIndex:**
- Eccellente per RAG avanzato (parent-child chunking, hybrid search, reranking)
- Meno overhead di LangChain per use case RAG
- Buone astrazioni per sorgenti dati diverse (PDF, SQL, API)

**Contro LlamaIndex:**
- Meno integrazioni tool/action rispetto a LangChain
- Meno flessibile per workflow non-RAG

## 3. AutoGen (Microsoft)

AutoGen è un framework per **conversazioni multi-agente**. La premessa: invece di un singolo agente che fa tutto, più agenti specializzati si passano messaggi e collaborano.

```python
import autogen

# Configurazione LLM
llm_config = {
    "config_list": [
        {
            "model": "claude-3-5-sonnet-20241022",
            "api_key": "sk-ant-...",
            "api_type": "anthropic"
        }
    ],
    "temperature": 0
}

# Agente assistente (LLM)
assistant = autogen.AssistantAgent(
    name="DevOps_Expert",
    llm_config=llm_config,
    system_message="""Sei un esperto DevOps senior. Quando scrivi codice o script,
    fornisci sempre esempi funzionanti. Termina con TERMINATE quando il task è completo."""
)

# Proxy umano (può eseguire codice o confermare)
user_proxy = autogen.UserProxyAgent(
    name="User",
    human_input_mode="NEVER",  # autonomo — non chiede conferma
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda msg: "TERMINATE" in msg.get("content", ""),
    code_execution_config={
        "work_dir": "/tmp/autogen_work",
        "use_docker": False  # True per sicurezza in produzione
    }
)

# Avvia conversazione
user_proxy.initiate_chat(
    assistant,
    message="Crea uno script Python che monitora il CPU usage di tutti i pod K8s ogni 30 secondi e invia alert su Slack se supera 80%"
)
```

### GroupChat — Multi-Agente Collaborativo

```python
# Scenario: code review con agenti specializzati
security_agent = autogen.AssistantAgent(
    name="Security_Reviewer",
    llm_config=llm_config,
    system_message="Sei un esperto di sicurezza. Analizza il codice per vulnerabilità."
)

performance_agent = autogen.AssistantAgent(
    name="Performance_Reviewer",
    llm_config=llm_config,
    system_message="Sei un esperto di performance. Analizza complessità e ottimizzazioni."
)

code_writer = autogen.AssistantAgent(
    name="Code_Writer",
    llm_config=llm_config,
    system_message="Scrivi codice pulito e applica i feedback ricevuti dagli altri reviewer."
)

user_proxy = autogen.UserProxyAgent(
    name="Manager",
    human_input_mode="NEVER",
    code_execution_config=False
)

# GroupChat: gli agenti si passano la parola automaticamente
groupchat = autogen.GroupChat(
    agents=[user_proxy, security_agent, performance_agent, code_writer],
    messages=[],
    max_round=12,
    speaker_selection_method="auto"  # LLM decide chi parla
)

manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

user_proxy.initiate_chat(
    manager,
    message="Review e ottimizza questa funzione Python:\n```python\ndef process_users(db_conn):\n    users = db_conn.execute('SELECT * FROM users WHERE active=1').fetchall()\n    for user in users:\n        send_email(user['email'], 'Welcome!')\n```"
)
```

**Pro AutoGen:**
- Multi-agent naturale e flessibile
- Esecuzione codice integrata con sandboxing Docker
- Buona gestione del flusso conversazionale

**Contro AutoGen:**
- Costo elevato (molte chiamate LLM per conversazione)
- Non deterministico — difficile da testare
- Meno adatto per workflow lineari semplici

## 4. CrewAI

CrewAI usa il paradigma **role-based**: gli agenti hanno un ruolo (role), un obiettivo (goal), e un backstory. Si organizzano in "crew" (equipaggi) con task assegnati.

```python
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool, FileReadTool

# Tool
search_tool = SerperDevTool()
file_tool = FileReadTool()

# Agenti con ruoli
researcher = Agent(
    role="DevOps Research Specialist",
    goal="Raccogliere informazioni aggiornate su best practice DevOps",
    backstory="Hai 15 anni di esperienza in DevOps e cloud native. Sei metodico e cerchi sempre le fonti primarie.",
    tools=[search_tool],
    llm="claude-3-5-sonnet-20241022",
    verbose=True
)

writer = Agent(
    role="Technical Documentation Writer",
    goal="Scrivere documentazione tecnica chiara e completa",
    backstory="Hai scritto documentazione tecnica per Google, AWS e altri top tech company.",
    tools=[file_tool],
    llm="claude-3-5-haiku-20241022",
    verbose=True
)

# Task
research_task = Task(
    description="Ricerca le best practice attuali per la sicurezza dei container Docker nel 2026",
    expected_output="Lista di 10 best practice con spiegazione e esempio per ognuna",
    agent=researcher
)

writing_task = Task(
    description="Trasforma i risultati della ricerca in una guida Markdown professionale",
    expected_output="File Markdown di 2000+ parole con esempi di codice",
    agent=writer,
    output_file="docker-security-guide.md"
)

# Crew (esecuzione sequenziale o parallela)
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,  # o Process.hierarchical
    verbose=True
)

result = crew.kickoff()
print(result)
```

**Pro CrewAI:**
- Astrazione intuitiva (role/goal/backstory)
- Buono per workflow con agenti specializzati chiari
- Integrazione con molti tool precostruiti

**Contro CrewAI:**
- Meno flessibile di LangGraph per workflow dinamici
- Task delegation non sempre ottimale
- API ancora in evoluzione

## 5. LangGraph

LangGraph è il framework più avanzato per agenti con **workflow stateful a grafo**. Invece di una catena lineare, il workflow è definito come un grafo di stati con transizioni condizionali.

```python
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from typing import TypedDict, Annotated, Sequence
import operator

# Definizione dello stato
class AgentState(TypedDict):
    messages: Annotated[Sequence[AIMessage | HumanMessage], operator.add]
    next_action: str
    iteration_count: int
    final_report: str

# LLM
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# Nodi del grafo
def analyze_alert(state: AgentState) -> dict:
    """Analizza l'alert e decide le azioni."""
    response = llm.invoke(state["messages"] + [
        HumanMessage(content="Analizza questo alert e decidi: devo raccogliere log? (sì/no)")
    ])
    return {
        "messages": [response],
        "next_action": "collect_logs" if "sì" in response.content.lower() else "generate_report"
    }

def collect_logs(state: AgentState) -> dict:
    """Raccoglie i log rilevanti."""
    # ... implementazione reale
    logs = "Logs raccolti: [ERROR] Connection timeout at 10:23:45"
    return {
        "messages": [HumanMessage(content=f"Logs: {logs}")],
        "next_action": "analyze_logs"
    }

def analyze_logs(state: AgentState) -> dict:
    """Analizza i log raccolti."""
    response = llm.invoke(state["messages"] + [
        HumanMessage(content="Analizza i log e identifica la root cause")
    ])
    return {
        "messages": [response],
        "next_action": "generate_report"
    }

def generate_report(state: AgentState) -> dict:
    """Genera il report finale."""
    response = llm.invoke(state["messages"] + [
        HumanMessage(content="Genera un report di incident analysis in JSON strutturato")
    ])
    return {
        "messages": [response],
        "final_report": response.content,
        "next_action": "end"
    }

def route(state: AgentState) -> str:
    """Router: decide il prossimo nodo in base allo stato."""
    return state["next_action"]

# Costruzione del grafo
workflow = StateGraph(AgentState)

# Aggiungi nodi
workflow.add_node("analyze_alert", analyze_alert)
workflow.add_node("collect_logs", collect_logs)
workflow.add_node("analyze_logs", analyze_logs)
workflow.add_node("generate_report", generate_report)

# Entry point
workflow.set_entry_point("analyze_alert")

# Edge condizionali
workflow.add_conditional_edges(
    "analyze_alert",
    route,
    {
        "collect_logs": "collect_logs",
        "generate_report": "generate_report"
    }
)
workflow.add_edge("collect_logs", "analyze_logs")
workflow.add_edge("analyze_logs", "generate_report")
workflow.add_edge("generate_report", END)

# Compila il grafo
app = workflow.compile()

# Esecuzione con checkpointing (permette di resumare il workflow)
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
app_with_checkpoints = workflow.compile(checkpointer=checkpointer)

initial_state = {
    "messages": [HumanMessage(content="ALERT: HighErrorRate - service=api-gateway - errors=45%")],
    "next_action": "",
    "iteration_count": 0,
    "final_report": ""
}

result = app.invoke(initial_state)
print(result["final_report"])
```

**Pro LangGraph:**
- Workflow complessi con condizioni e loop
- Stato persistente e checkpointing
- Debugging visuale del grafo
- Più prevedibile e testabile di AutoGen

**Contro LangGraph:**
- Curva di apprendimento ripida
- Verboso per workflow semplici
- Ancora relativamente giovane (cambia spesso)

## Confronto Framework

| Framework | Ideale per | Complessità | Debugging | Maturità |
|-----------|-----------|-------------|---------|---------|
| **LangChain** | RAG, chain semplici, tante integrazioni | Media | Medio | Alta |
| **LlamaIndex** | RAG avanzato, indexing dati strutturati | Media | Buono | Alta |
| **AutoGen** | Multi-agent conversazionale, esecuzione codice | Alta | Difficile | Media |
| **CrewAI** | Role-based multi-agent, workflow chiari | Media | Medio | Media |
| **LangGraph** | Workflow stateful complessi, loop condizionali | Alta | Buono | Media |
| **Custom (SDK)** | Task semplici, massimo controllo, produzione | Bassa | Ottimo | N/A |

## Quando Usare Framework vs Implementazione Custom

**Usa un framework se:**
- Hai bisogno di molte integrazioni precostruite (vector store, loader, tool)
- Il workflow è genuinamente complesso (multi-agent, loop condizionali, stato)
- Il tuo team conosce già il framework
- Il tempo to market è prioritario rispetto alla manutenibilità

**Usa implementazione custom (SDK diretto) se:**
- Il task è relativamente lineare (1-3 chiamate LLM)
- La performance e il controllo sono critici
- Vuoi debugging facile e full observability
- Il codice andrà in produzione con SLA stringenti
- Non vuoi dipendere da breaking changes di un framework

!!! tip "Regola empirica"
    Prova prima con l'SDK diretto del provider. Se arrivi a 200+ righe di boilerplate per gestire tool, routing, o stato — allora considera un framework. Spesso 200 righe di codice custom sono più manutenibili di 20 righe con un framework che nasconde 2000 righe di magia.

## Riferimenti

- [LangChain Documentation](https://python.langchain.com/docs/) — Documentazione ufficiale e cookbook
- [LlamaIndex Documentation](https://docs.llamaindex.ai/) — Guide e tutorial
- [AutoGen GitHub](https://github.com/microsoft/autogen) — Framework Microsoft multi-agent
- [CrewAI Documentation](https://docs.crewai.com/) — Framework role-based
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) — Workflow stateful
- [LiteLLM](https://docs.litellm.ai/) — Proxy unificato, agnostico dal framework
