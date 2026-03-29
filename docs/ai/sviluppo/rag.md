---
title: "RAG — Retrieval-Augmented Generation"
slug: rag
category: ai
tags: [rag, retrieval, vector-database, embeddings, semantic-search, qdrant, pinecone, chunking]
search_keywords: [RAG, Retrieval-Augmented Generation, vector database, embedding, semantic search, similarity search, Qdrant, Pinecone, Weaviate, ChromaDB, pgvector, FAISS, chunking, reranking, BM25 hybrid search, HyDE, RAGAS, sentence-transformers, bge-m3, text-embedding]
parent: ai/sviluppo/_index
related: [ai/sviluppo/_index, ai/sviluppo/prompt-engineering, ai/tokens-context/context-window, ai/training/valutazione]
official_docs: https://qdrant.tech/documentation/
status: needs-review
difficulty: advanced
last_updated: 2026-03-28
---

# RAG — Retrieval-Augmented Generation

## Panoramica

RAG (Retrieval-Augmented Generation) è il pattern architetturale che permette agli LLM di accedere a knowledge base aggiornate e private senza richiedere fine-tuning o la memorizzazione di tutti i dati nel training. L'idea fondamentale è semplice: invece di chiedere al modello di ricordare tutto, gli forniamo le informazioni rilevanti al momento della query, recuperandole da una knowledge base esterna.

RAG risolve i tre problemi principali degli LLM stand-alone: il **knowledge cutoff** (il modello non sa cosa è successo dopo il suo training), la **mancanza di dati privati** (la documentazione interna non è nel training), e le **hallucination** (il modello inventa dettagli quando non sa). Un sistema RAG ben implementato risponde "Non trovo questa informazione nella documentazione" invece di inventare. In ambito DevOps, RAG è lo strumento giusto per chatbot su runbook interni, Q&A su documentazione di architettura, e analisi di incident history.

## 1. Architettura Base RAG

```
FASE OFFLINE (ingestion):
Documents → Chunking → Embedding → Vector Store

FASE ONLINE (query):
Query → Embed Query → Vector Search → Top-K Chunks
      → Rerank (opzionale) → Augment Prompt → LLM → Response
```

```python
# Pipeline RAG end-to-end con Qdrant + sentence-transformers + Claude
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
import anthropic
import uuid

# Setup
embedding_model = SentenceTransformer("BAAI/bge-m3")  # multilingual
qdrant = QdrantClient(":memory:")  # o QdrantClient(host="localhost", port=6333)
claude = anthropic.Anthropic()

COLLECTION_NAME = "devops_kb"
EMBEDDING_DIM = 1024  # bge-m3 dimensione

# Crea collection
qdrant.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE)
)

# Fase 1: Ingestion
def ingest_documents(documents: list[dict]) -> None:
    """Ingesta documenti nel vector store."""
    texts = [doc["content"] for doc in documents]
    embeddings = embedding_model.encode(texts, normalize_embeddings=True).tolist()

    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={"content": doc["content"], "source": doc["source"], "title": doc.get("title", "")}
            )
            for doc, embedding in zip(documents, embeddings)
        ]
    )

# Fase 2: Query
def rag_query(query: str, k: int = 5) -> str:
    """Risponde a una query usando RAG."""
    # Embed query
    query_embedding = embedding_model.encode([query], normalize_embeddings=True)[0].tolist()

    # Retrieve
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        limit=k,
        with_payload=True
    )

    # Build context
    context_parts = []
    for i, result in enumerate(results):
        context_parts.append(
            f"[Documento {i+1}] Fonte: {result.payload['source']}\n"
            f"Score: {result.score:.3f}\n"
            f"{result.payload['content']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # Generate
    response = claude.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system="""Rispondi alle domande basandoti ESCLUSIVAMENTE sulla documentazione fornita.
Cita sempre la fonte (es. "Secondo [Documento 2]...").
Se la risposta non è presente, dì: "Non trovo questa informazione nella documentazione disponibile."
Non inventare informazioni che non sono nel contesto.""",
        messages=[{
            "role": "user",
            "content": f"<context>\n{context}\n</context>\n\nDomanda: {query}"
        }]
    )
    return response.content[0].text
```

## 2. Chunking Strategies

Il chunking è il processo di suddivisione dei documenti in pezzi più piccoli (chunk) per l'indicizzazione. La strategia di chunking ha un impatto enorme sulla qualità del retrieval.

### Fixed Size Chunking

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Recursive Text Splitter: prova prima a spezzare su separatori semantici
# poi su spazio, poi su carattere se necessario
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,        # token target per chunk (approssimativo per parole)
    chunk_overlap=200,      # overlap tra chunk consecutivi (20%)
    separators=["\n\n", "\n", ". ", " ", ""],  # priorità separatori
    length_function=len     # o usa tiktoken per misurare in token reali
)

chunks = splitter.split_text(document_text)
```

### Token-Aware Chunking

```python
import tiktoken

def chunk_by_tokens(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Chunking preciso basato su token count (non caratteri)."""
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append(chunk_text)
        start += chunk_size - overlap

    return chunks
```

### Semantic Chunking

```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

# Spezza il testo dove cambia il significato semantico
# Invece di usare dimensioni fisse, trova i breakpoint "naturali"
embeddings = OpenAIEmbeddings()
semantic_splitter = SemanticChunker(
    embeddings,
    breakpoint_threshold_type="percentile",  # o "standard_deviation"
    breakpoint_threshold_amount=95  # spezza dove similarity < 95° percentile
)
chunks = semantic_splitter.split_text(document_text)
```

### Document Structure Aware

```python
import re
from typing import Generator

def chunk_markdown_by_sections(markdown_text: str) -> Generator[dict, None, None]:
    """Chunking basato sulla struttura Markdown: ogni sezione H2 diventa un chunk."""
    sections = re.split(r'\n## ', markdown_text)

    for i, section in enumerate(sections):
        if i == 0:
            # Prima sezione (prima del primo H2) — solitamente frontmatter/intro
            if section.strip():
                yield {"content": section.strip(), "section": "intro", "level": 0}
        else:
            # Estrai il titolo e il contenuto
            lines = section.split('\n', 1)
            title = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""

            # Se la sezione è troppo lunga, spezzala ulteriormente su H3
            if len(content) > 3000:
                subsections = re.split(r'\n### ', content)
                for j, sub in enumerate(subsections):
                    sub_lines = sub.split('\n', 1)
                    sub_title = sub_lines[0].strip() if j > 0 else title
                    sub_content = sub_lines[1].strip() if len(sub_lines) > 1 else sub
                    yield {
                        "content": f"## {title}\n### {sub_title}\n\n{sub_content}" if j > 0 else f"## {title}\n\n{sub_content}",
                        "section": f"{title} / {sub_title}" if j > 0 else title,
                        "level": 2
                    }
            else:
                yield {"content": f"## {title}\n\n{content}", "section": title, "level": 2}
```

### Trade-off Chunk Size

| Chunk Size | Vantaggi | Svantaggi | Use Case |
|-----------|---------|---------|---------|
| Piccolo (100-300 token) | Retrieval preciso, meno rumore | Perde contesto, più chunk | FAQ, definizioni |
| Medio (500-1000 token) | Buon balance | Standard per la maggior parte dei task | Documentazione tecnica |
| Grande (1000-2000 token) | Preserva contesto completo | Rumore, meno preciso | Documenti lunghi con dipendenze |

## 3. Embedding Models

Gli embedding model trasformano il testo in vettori numerici dove testi semanticamente simili hanno vettori vicini.

### Modelli di Embedding

| Modello | Dimensioni | Lingue | Note |
|---------|-----------|--------|------|
| **text-embedding-3-small** (OpenAI) | 1536 | Multilingual | Economico, buona qualità |
| **text-embedding-3-large** (OpenAI) | 3072 | Multilingual | Qualità superiore, più costoso |
| **bge-m3** (BAAI) | 1024 | 100+ lingue | Open source, ottimo per italiano |
| **bge-large-en-v1.5** | 1024 | Inglese | Benchmark MTEB eccellente per EN |
| **e5-large-v2** (Microsoft) | 1024 | Multilingual | Solido e stabile |
| **nomic-embed-text-v1.5** | 768 | EN | Open source, lunga context window (8K) |
| **jina-embeddings-v3** | 1024 | Multilingual | Ottimo per codice e testo tecnico |

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# bge-m3: eccellente per italiano e testo tecnico DevOps
model = SentenceTransformer("BAAI/bge-m3")

# Nota: bge-m3 supporta query instruction per migliorare la ricerca
query = "Come si configura un LoadBalancer su Kubernetes?"
documents = [
    "Un Service di tipo LoadBalancer espone il deployment su un IP esterno...",
    "Per creare un LoadBalancer AWS: annotate il Service con service.beta.kubernetes.io/aws-load-balancer-type"
]

# Per bge-m3, le query beneficiano da un prefix "Represent this sentence for searching relevant passages:"
# ma i documenti no
query_emb = model.encode(query, normalize_embeddings=True)
doc_embs = model.encode(documents, normalize_embeddings=True)

# Similarity scores
scores = np.dot(doc_embs, query_emb)
best_idx = np.argmax(scores)
print(f"Documento più rilevante (score {scores[best_idx]:.3f}):\n{documents[best_idx]}")
```

## 4. Vector Databases

I vector database sono ottimizzati per similarity search su vettori ad alta dimensione.

### Qdrant — Open Source, Alta Performance

```python
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

# Connessione
qdrant = QdrantClient(host="localhost", port=6333)  # self-hosted
# oppure: QdrantClient(url="https://xyz.qdrant.tech", api_key="...")  # cloud

# Crea collection con indexing HNSW
qdrant.create_collection(
    collection_name="devops_docs",
    vectors_config=models.VectorParams(
        size=1024,
        distance=models.Distance.COSINE,
        on_disk=False  # True per dataset grandi
    ),
    hnsw_config=models.HnswConfigDiff(
        m=16,           # numero di connessioni per nodo (qualità vs RAM)
        ef_construct=100  # dimensione lista durante costruzione (qualità vs velocità)
    ),
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000  # usa mmap per collection grandi
    )
)

# Upsert con payload strutturato
qdrant.upsert(
    collection_name="devops_docs",
    points=[
        models.PointStruct(
            id=1,
            vector=[0.1, 0.2, ...],  # embedding
            payload={
                "content": "...",
                "source": "docs/kubernetes/ingress.md",
                "category": "kubernetes",
                "last_updated": "2026-02-27"
            }
        )
    ]
)

# Search base
results = qdrant.search(
    collection_name="devops_docs",
    query_vector=query_embedding,
    limit=5,
    with_payload=True,
    score_threshold=0.7  # filtra risultati con score < 0.7
)

# Search con filtri
results = qdrant.search(
    collection_name="devops_docs",
    query_vector=query_embedding,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value="kubernetes")
            ),
            models.FieldCondition(
                key="last_updated",
                range=models.Range(gte="2025-01-01")
            )
        ]
    ),
    limit=5
)
```

### pgvector — PostgreSQL Extension

```sql
-- Abilitare estensione
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabella con vettore
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    source VARCHAR(500),
    category VARCHAR(100),
    embedding vector(1024),  -- dimensione del modello
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index HNSW per ricerca veloce
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Similarity search
SELECT id, content, source,
       1 - (embedding <=> $1::vector) AS similarity
FROM documents
WHERE category = 'kubernetes'
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

```python
import psycopg2
import numpy as np

conn = psycopg2.connect("postgresql://user:pass@localhost/mydb")

def search_pgvector(query_embedding: list[float], k: int = 5, category: str = None) -> list[dict]:
    """Ricerca semantica con pgvector."""
    with conn.cursor() as cur:
        query_filter = "WHERE category = %s" if category else ""
        params = [query_embedding, k]
        if category:
            params.insert(1, category)

        cur.execute(f"""
            SELECT id, content, source,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM documents
            {query_filter}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [query_embedding] + ([category] if category else []) + [query_embedding, k])

        return [{"id": r[0], "content": r[1], "source": r[2], "similarity": r[3]}
                for r in cur.fetchall()]
```

### ChromaDB — Per Sviluppo Locale

```python
import chromadb
from chromadb.utils import embedding_functions

# Setup in-memory per sviluppo
client = chromadb.Client()
# oppure: chromadb.PersistentClient(path="./chroma_db")

# Usa embedding function preconfigurata
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key="sk-...",
    model_name="text-embedding-3-small"
)

collection = client.create_collection(
    name="devops_docs",
    embedding_function=openai_ef,
    metadata={"hnsw:space": "cosine"}
)

# Add documents (ChromaDB gestisce automaticamente gli embedding)
collection.add(
    documents=["Kubernetes è un sistema di orchestrazione...", "Helm è il package manager..."],
    metadatas=[{"source": "k8s.md"}, {"source": "helm.md"}],
    ids=["id1", "id2"]
)

# Query
results = collection.query(
    query_texts=["Come funziona il rolling update?"],
    n_results=3,
    where={"source": "k8s.md"}  # filtro metadata
)
```

### Confronto Vector Database

| Database | Tipo | Hosting | Performance | Filtri | Ideal per |
|----------|------|---------|-------------|--------|---------|
| **Qdrant** | Dedicato | Self/Cloud | Alta | Avanzati | Produzione, open source |
| **Pinecone** | Managed | Cloud only | Alta | Medi | Managed, serverless |
| **Weaviate** | Dedicato | Self/Cloud | Alta | GraphQL | Schema strutturato |
| **pgvector** | Estensione PG | Self | Media | SQL completo | Già usando PostgreSQL |
| **ChromaDB** | Embedded/Server | Self | Media | Semplici | Sviluppo, prototipi |
| **FAISS** | Libreria | Self (in-process) | Molto Alta | No | Ricerca pura, memoria |

## 5. Advanced RAG

### Hybrid Search — Vector + BM25

La hybrid search combina la ricerca semantica (vettoriale) con la ricerca keyword (BM25). Cattura sia la similarità semantica che le corrispondenze esatte di termini tecnici (nomi di funzioni, comandi, acronimi).

```python
from qdrant_client import models

# Qdrant supporta natively hybrid search con sparse vectors
# Configurazione collection con vettori densi e sparsi
qdrant.create_collection(
    collection_name="hybrid_docs",
    vectors_config={
        "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams()  # BM25-like
    }
)

# Ricerca ibrida con query fusion (RRF - Reciprocal Rank Fusion)
results = qdrant.query_points(
    collection_name="hybrid_docs",
    prefetch=[
        models.Prefetch(
            query=dense_query_vector,
            using="dense",
            limit=20
        ),
        models.Prefetch(
            query=models.SparseVector(indices=[...], values=[...]),
            using="sparse",
            limit=20
        )
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),  # Reciprocal Rank Fusion
    limit=5
)
```

### Reranking

Dopo il retrieval iniziale (che recupera K=20-50 candidati), il reranker valuta ogni documento rispetto alla query con un modello più preciso (cross-encoder) e riordina.

```python
from sentence_transformers import CrossEncoder

# Cross-encoder: valuta la coppia (query, documento) insieme
# Molto più preciso di un bi-encoder ma lento (non scalabile per vector search)
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, documents: list[str], top_k: int = 5) -> list[tuple[int, float]]:
    """Rerank documenti usando un cross-encoder."""
    pairs = [(query, doc) for doc in documents]
    scores = reranker.predict(pairs)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]

# Pipeline completa con reranking
def rag_with_reranking(query: str) -> str:
    # Step 1: retrieval ampio (50 candidati)
    initial_results = vector_search(query, k=50)
    documents = [r.payload["content"] for r in initial_results]

    # Step 2: rerank per selezionare i top 5
    reranked = rerank(query, documents, top_k=5)
    top_docs = [documents[idx] for idx, score in reranked]

    # Step 3: genera risposta con i 5 doc migliori
    context = "\n\n".join(top_docs)
    return generate_answer(query, context)
```

Modelli di reranking:
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — leggero, veloce
- `BAAI/bge-reranker-v2-m3` — multilingual, ottimo per italiano
- `Cohere Rerank API` — managed, alta qualità, pay-per-use

### HyDE — Hypothetical Document Embeddings

```python
def hyde_search(query: str, k: int = 5) -> list[str]:
    """HyDE: genera un documento ipotetico e cerca documenti simili."""

    # Step 1: LLM genera una risposta ipotetica (senza recupero)
    hypothetical_doc = claude.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Scrivi un paragrafo che risponde a questa domanda tecnica: {query}"
        }]
    ).content[0].text

    # Step 2: Embed il documento ipotetico
    hyde_embedding = embedding_model.encode(hypothetical_doc, normalize_embeddings=True).tolist()

    # Step 3: Cerca nel vector store usando l'embedding del documento ipotetico
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=hyde_embedding,
        limit=k
    )

    return [r.payload["content"] for r in results]

# HyDE funziona meglio quando la query è breve ma la risposta attesa è lunga
# Es: "Kubernetes RBAC" → il documento ipotetico parla di ClusterRole, RoleBinding, etc.
# L'embedding del documento ipotetico è più vicino alla documentazione reale
```

### Multi-Query Retrieval

```python
def multi_query_rag(query: str, k: int = 5) -> str:
    """Genera varianti della query e fa retrieval con ognuna."""

    # Genera 3 varianti della query
    variants_prompt = f"""Genera 3 varianti diverse della seguente query di ricerca.
Le varianti devono coprire aspetti diversi della stessa domanda.
Restituisci SOLO le 3 query, una per riga.

Query originale: {query}"""

    variants_text = claude.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=200,
        messages=[{"role": "user", "content": variants_prompt}]
    ).content[0].text

    all_queries = [query] + variants_text.strip().split("\n")[:3]

    # Retrieval per ogni variante
    all_results = {}
    for q in all_queries:
        q_emb = embedding_model.encode(q, normalize_embeddings=True).tolist()
        results = qdrant.search(collection_name=COLLECTION_NAME, query_vector=q_emb, limit=k)
        for r in results:
            doc_id = r.id
            if doc_id not in all_results or all_results[doc_id]["score"] < r.score:
                all_results[doc_id] = {"content": r.payload["content"], "score": r.score}

    # Prendi i top-k unici
    top_docs = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)[:k]
    return generate_answer(query, "\n\n".join([d["content"] for d in top_docs]))
```

### Parent-Child Chunking

```python
# I chunk piccoli vengono usati per la ricerca precisa
# Ma quando trovati, si espande al chunk parent per avere più contesto

def build_parent_child_index(documents: list[str]) -> dict:
    """Crea index parent-child: child per retrieval, parent per lettura."""
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=100)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)

    index = {}  # child_id -> parent_content

    for doc in documents:
        parents = parent_splitter.split_text(doc)
        for parent in parents:
            children = child_splitter.split_text(parent)
            for child in children:
                child_id = hash(child)
                index[child_id] = parent  # child -> parent mapping
                # Inserisci child nel vector store con il suo parent_id
                embed_and_store(child, metadata={"parent_id": child_id, "parent": parent})

    return index

def parent_child_search(query: str, k: int = 3) -> list[str]:
    """Cerca nei child chunks, restituisce i parent chunks."""
    child_results = vector_search(query, k=k*3)  # più candidati per i child
    parent_ids_seen = set()
    parent_contents = []

    for result in child_results:
        parent_id = result.payload.get("parent_id")
        if parent_id and parent_id not in parent_ids_seen:
            parent_ids_seen.add(parent_id)
            parent_contents.append(result.payload.get("parent", result.payload["content"]))
            if len(parent_contents) == k:
                break

    return parent_contents
```

## 6. Valutazione RAG

### Metriche RAGAS

```python
# pip install ragas
from ragas import evaluate
from ragas.metrics import (
    faithfulness,          # La risposta è supportata dal contesto?
    answer_relevancy,      # La risposta è rilevante alla domanda?
    context_precision,     # Il contesto recuperato è preciso (poca ridondanza)?
    context_recall,        # Il contesto recuperato è completo?
)
from datasets import Dataset

# Dataset di test
test_data = {
    "question": ["Come si configura un Ingress nginx?"],
    "answer": ["Per configurare un Ingress nginx, crea un oggetto Ingress..."],
    "contexts": [["# Ingress\nUn Ingress gestisce l'accesso esterno..."]],
    "ground_truth": ["Un Ingress nginx richiede l'installazione del controller..."]
}

dataset = Dataset.from_dict(test_data)
result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)
print(result)
# Scores da 0 a 1 per ogni metrica
```

### Evaluation Manuale Strutturata

```python
# Framework per valutazione manuale
eval_cases = [
    {
        "query": "Come si aggiorna un Deployment senza downtime?",
        "expected_mentions": ["rolling update", "strategy", "maxSurge", "maxUnavailable"],
        "must_cite_source": True,
        "acceptable_sources": ["docs/kubernetes/deployments.md"]
    }
]

def evaluate_rag_response(
    query: str,
    response: str,
    source_docs: list[str],
    expected_mentions: list[str],
    must_cite_source: bool
) -> dict:
    """Valuta una risposta RAG con criteri strutturati."""
    results = {}

    # Check 1: tutti i termini attesi sono presenti?
    results["completeness"] = all(
        term.lower() in response.lower() for term in expected_mentions
    )
    results["missing_terms"] = [t for t in expected_mentions if t.lower() not in response.lower()]

    # Check 2: la risposta cita le fonti?
    results["cites_source"] = any(src in response for src in source_docs) if must_cite_source else True

    # Check 3: nessuna informazione inventata? (usa LLM-as-judge)
    results["faithfulness_score"] = llm_faithfulness_check(response, source_docs)

    return results
```

## 7. Esempio Completo — RAG su Knowledge Base DevOps

```python
"""
Sistema RAG completo per knowledge base DevOps.
"""
import anthropic
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer, CrossEncoder
from pathlib import Path
import uuid

class DevOpsKnowledgeBase:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.qdrant = QdrantClient(":memory:")  # o persistente
        self.embedder = SentenceTransformer("BAAI/bge-m3")
        self.reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
        self.collection = "devops_kb"
        self._init_collection()

    def _init_collection(self):
        self.qdrant.recreate_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE)
        )

    def ingest_markdown_dir(self, docs_path: str) -> int:
        """Ingesta tutti i file .md da una directory."""
        total = 0
        for md_file in Path(docs_path).rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            chunks = self._chunk_markdown(text, str(md_file))
            self._embed_and_store(chunks)
            total += len(chunks)
        return total

    def _chunk_markdown(self, text: str, source: str) -> list[dict]:
        """Chunking con overlap, consapevole della struttura Markdown."""
        sections = text.split("\n## ")
        chunks = []
        for section in sections:
            if len(section) > 1500:
                # Spezza sezioni grandi
                words = section.split()
                for i in range(0, len(words), 200):
                    chunk_words = words[i:i+250]
                    chunks.append({"content": " ".join(chunk_words), "source": source})
            else:
                chunks.append({"content": section, "source": source})
        return chunks

    def _embed_and_store(self, chunks: list[dict]):
        contents = [c["content"] for c in chunks]
        embeddings = self.embedder.encode(contents, normalize_embeddings=True).tolist()
        self.qdrant.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb,
                    payload={"content": chunk["content"], "source": chunk["source"]}
                )
                for chunk, emb in zip(chunks, embeddings)
            ]
        )

    def query(self, question: str, k: int = 3) -> str:
        """Query con retrieval + reranking + generation."""
        # Retrieve candidati
        q_emb = self.embedder.encode([question], normalize_embeddings=True)[0].tolist()
        candidates = self.qdrant.search(
            collection_name=self.collection,
            query_vector=q_emb,
            limit=20,
            score_threshold=0.5
        )

        if not candidates:
            return "Non ho trovato informazioni rilevanti per questa domanda."

        # Rerank
        doc_texts = [c.payload["content"] for c in candidates]
        pairs = [(question, doc) for doc in doc_texts]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        top_k = ranked[:k]

        # Costruisci context
        context = "\n\n---\n\n".join([
            f"**Fonte:** {c.payload['source']} (score: {score:.3f})\n{c.payload['content']}"
            for c, score in top_k
        ])

        # Generate
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system="""Sei un assistente tecnico per team DevOps.
Rispondi basandoti ESCLUSIVAMENTE sulla documentazione fornita.
Cita sempre la fonte specifica (nome del file).
Se l'informazione non è nella documentazione, dì esplicitamente "Non ho questa informazione."
Usa formato Markdown con code blocks per i comandi.""",
            messages=[{
                "role": "user",
                "content": f"<documentation>\n{context}\n</documentation>\n\nDomanda: {question}"
            }]
        )
        return response.content[0].text


# Utilizzo
kb = DevOpsKnowledgeBase()
kb.ingest_markdown_dir("./docs")
print(kb.query("Come si configura l'autoscaling orizzontale in Kubernetes?"))
```

## Best Practices

- **Chunk overlap del 15-25%**: previene la perdita di informazioni ai confini dei chunk. Troppo overlap aumenta il rumore.
- **Chunk size in token, non caratteri**: usa tiktoken o il tokenizer del tuo modello di embedding per misurare la dimensione dei chunk in modo preciso.
- **Sempre score threshold**: filtra i risultati sotto 0.6-0.7 di similarity cosine. Risultati irrilevanti degradano la risposta.
- **Reranking sempre in produzione**: il primo retrieval (bi-encoder) è veloce ma impreciso. Il reranker migliora significativamente la qualità.
- **Metadata ricchi**: aggiungi sempre source, date, category, tipo_documento ai payload. Permettono filtri che riducono il rumore.
- **Testa con RAGAS**: misura faithfulness, answer_relevancy, context_precision prima del deployment.
- **Versiona gli embedding**: se cambi modello di embedding, devi re-embeddare tutto il corpus. Traccia quale modello hai usato per ogni chunk.
- **Refresh periodico**: i documenti cambiano. Implementa un pipeline di re-ingestion periodica.

## Troubleshooting

### Scenario 1 — Score di similarity bassi: tutti i risultati sotto 0.5

**Sintomo:** Il vector search restituisce documenti con score molto bassi (0.2-0.4) o nessun risultato supera il threshold. La qualità delle risposte è scadente perché il contesto è irrilevante.

**Causa:** Mismatch tra il modello di embedding usato in ingestion e quello in query, documenti e query in lingue diverse senza un modello multilingual, o chunking eccessivamente granulare che perde il contesto semantico.

**Soluzione:** Verifica che ingestion e query usino lo stesso modello. Per corpora misti italiano/inglese, usa un modello multilingual come `bge-m3`.

```python
# Debugging: confronta embedding di query e documento
def debug_similarity(query: str, doc: str, model_name: str = "BAAI/bge-m3"):
    model = SentenceTransformer(model_name)
    q_emb = model.encode(query, normalize_embeddings=True)
    d_emb = model.encode(doc, normalize_embeddings=True)
    score = float(np.dot(q_emb, d_emb))
    print(f"Similarity: {score:.4f}")
    # Se < 0.3 con documenti chiaramente rilevanti → problema di modello o lingua

# Abbassa il threshold temporaneamente per diagnosticare
results = qdrant.search(
    collection_name=COLLECTION_NAME,
    query_vector=query_embedding,
    limit=10,
    # score_threshold=0.7  # commenta per vedere tutti i risultati
)
for r in results:
    print(f"Score {r.score:.3f}: {r.payload['content'][:100]}")
```

---

### Scenario 2 — Hallucinations: il modello inventa informazioni non nel contesto

**Sintomo:** Il modello risponde con dettagli plausibili ma non presenti in nessuno dei documenti recuperati. Spesso non cita le fonti o cita documenti che non contengono l'informazione riportata.

**Causa:** Il system prompt non vincola abbastanza il modello a usare solo il contesto fornito. Il modello usa la sua conoscenza parametrica quando il contesto è insufficiente.

**Soluzione:** Rafforza il vincolo nel system prompt e aggiungi verifiche post-generazione.

```python
# System prompt con vincoli espliciti anti-hallucination
STRICT_SYSTEM = """Rispondi ESCLUSIVAMENTE con informazioni presenti nella documentazione fornita.
REGOLE NON DEROGABILI:
1. Se la risposta non è nella documentazione, scrivi: "INFORMAZIONE NON DISPONIBILE: questa informazione non è presente nella documentazione fornita."
2. Ogni affermazione deve essere seguita dalla fonte tra parentesi quadre: [Fonte: nome_file.md]
3. NON usare la tua conoscenza generale. Agisci come se non sapessi nulla al di fuori dei documenti.
4. Se i documenti sono parzialmente rilevanti, rispondi solo per la parte coperta e segnala i gap."""

# Post-processing: verifica che ogni fonte citata esista nel contesto
def verify_citations(response: str, source_docs: list[dict]) -> dict:
    available_sources = {doc["source"] for doc in source_docs}
    # Estrai fonti citate nella risposta
    cited = re.findall(r'\[Fonte: ([^\]]+)\]', response)
    invalid = [c for c in cited if c not in available_sources]
    return {
        "has_hallucinated_sources": bool(invalid),
        "invalid_citations": invalid,
        "response_is_safe": not invalid
    }
```

---

### Scenario 3 — Risposta incompleta nonostante documenti pertinenti nel corpus

**Sintomo:** Il sistema RAG risponde "Non ho trovato informazioni" o dà risposte parziali, ma i documenti rilevanti esistono nella knowledge base. Verificato cercando manualmente nel corpus.

**Causa:** Il chunking ha spezzato le informazioni chiave in punti scomodi, la dimensione dei chunk è troppo piccola rispetto alla complessità della query, o il threshold di similarity è troppo alto.

**Soluzione:** Diagnostica il retrieval con query diverse, prova chunking strategy alternative, e considera hybrid search o HyDE.

```python
# Diagnosi: test del retrieval isolato
def diagnose_retrieval(query: str, expected_source: str) -> None:
    """Verifica se il documento atteso è raggiungibile."""
    q_emb = embedding_model.encode(query, normalize_embeddings=True).tolist()

    # Cerca senza threshold per vedere dove si posiziona il documento atteso
    all_results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=q_emb,
        limit=50  # ampio
    )

    for rank, r in enumerate(all_results):
        if expected_source in r.payload.get("source", ""):
            print(f"Trovato al rank {rank+1} con score {r.score:.3f}")
            break
    else:
        print(f"PROBLEMA: '{expected_source}' non trovato nei top-50 risultati")
        print("→ Verifica che il documento sia stato ingested correttamente")
        print("→ Prova HyDE o multi-query retrieval")

# Se il documento è al rank 30 con score 0.55:
# → Score threshold di 0.7 lo stava filtrando → abbassa o usa reranking
# → Rank 30 con score 0.55 → prova chunking più grande o HyDE
```

---

### Scenario 4 — Latency alta in produzione (>3s per query)

**Sintomo:** Il sistema RAG è troppo lento per un'interfaccia interattiva. Il profiling mostra che il collo di bottiglia è nel reranker o nell'embedding della query.

**Causa:** Il cross-encoder reranker valuta N coppie (query, doc) in sequenza. Con N=50 candidati e un modello di reranking di medie dimensioni, il tempo di reranking può superare 1-2 secondi su CPU.

**Soluzione:** Riduci i candidati pre-reranking, usa un reranker leggero, oppure parallelizza con asyncio o sposta il reranking su GPU.

```python
import time
from functools import lru_cache

# Profiling semplice
def timed_rag_query(query: str) -> tuple[str, dict]:
    timings = {}

    t0 = time.perf_counter()
    q_emb = embedding_model.encode(query, normalize_embeddings=True).tolist()
    timings["embedding_ms"] = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    candidates = qdrant.search(collection_name=COLLECTION_NAME, query_vector=q_emb, limit=20)
    timings["retrieval_ms"] = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    pairs = [(query, c.payload["content"]) for c in candidates]
    scores = reranker.predict(pairs)
    timings["reranking_ms"] = (time.perf_counter() - t2) * 1000

    # Se reranking_ms > 1000ms → collo di bottiglia
    # Opzioni: usa cross-encoder/ms-marco-MiniLM-L-6-v2 (più leggero)
    # oppure riduci candidati da 20 a 10

    t3 = time.perf_counter()
    response = generate_answer(query, candidates[:5])
    timings["llm_ms"] = (time.perf_counter() - t3) * 1000

    return response, timings

# Cache embedding per query frequenti (identiche)
@lru_cache(maxsize=1000)
def cached_embed(query: str) -> tuple:
    return tuple(embedding_model.encode(query, normalize_embeddings=True).tolist())
```

---

## Riferimenti

- [Qdrant Documentation](https://qdrant.tech/documentation/) — Vector DB open source
- [RAGAS — RAG Evaluation Framework](https://docs.ragas.io/) — Valutazione sistematica
- [BGE-M3 Technical Report](https://arxiv.org/abs/2309.07597) — Modello embedding multilingua open source
- [Advanced RAG (Yunfan Gao et al., 2024)](https://arxiv.org/abs/2312.10997) — Survey sulle tecniche RAG avanzate
- [HyDE (Luyu Gao et al., 2022)](https://arxiv.org/abs/2212.10496) — Hypothetical Document Embeddings
