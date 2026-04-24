# Step 5: Knowledge Base + GraphRAG
## CPG Supply Chain — Document Ingestion, Vector Embeddings & Hybrid Agent

> **What this step builds:** Your unstructured documents (PDFs, Word files,
> SOPs, vendor contracts, quality manuals) are chunked, embedded, and stored
> as vector-indexed nodes in Neo4j Aura — linked directly to your existing
> graph entities. The Step 4 agent is then upgraded to a **hybrid agent**
> that combines structured graph traversal WITH semantic document search
> in a single query. This is the full GraphRAG pattern.

---

## What GraphRAG Means in Your Context

```
Pure Graph Query (Step 4):
  "Which vendors are at high risk?"
  → Cypher traversal → rows from enriched nodes → answer

Pure RAG (vector search only):
  "What is the vendor scorecard policy?"
  → Embed question → find similar doc chunks → answer

GraphRAG (this step — both together):
  "How should I rebalance supply for high-risk vendors
   based on our procurement policy?"
  → Find high-risk vendors via Cypher           (structured)
  → Find procurement SOP chunks via vectors     (unstructured)
  → LLM synthesizes BOTH into one answer        (grounded)
```

The key difference: answers are grounded in BOTH live supply chain data
AND your institutional knowledge documents simultaneously.

---

## Architecture of What You Are Building

```
Your Documents (PDFs, DOCX, TXT)
          │
          ▼
   [ Document Loader ]          LangChain loaders per file type
          │
          ▼
   [ Text Splitter ]            Chunk into ~500 token segments
          │
          ▼
   [ Embedding Model ]          sentence-transformers (local, free) → float vectors
          │
          ▼
   [ Neo4j Aura ]               Store as :KnowledgeChunk nodes
   Vector Index                 with embedding property
          │
          ▼ linked via relationships
   [ Existing Graph Nodes ]     Vendor, Product, Plant, etc.
   (Vendor)-[:HAS_DOCUMENT]->(:KnowledgeChunk)

                    ↓ at query time ↓

   User Question
      │              │
      ▼              ▼
  Cypher         Vector Search
  (graph data)   (doc chunks)
      │              │
      └──────┬────────┘
             ▼
      [ LLM synthesis ]
             ▼
      Hybrid Answer
```

---

## Before You Start — Checklist

```
✅ Step 4 complete — FastAPI agent running, chatbox working
✅ ontology_mock/ project folder exists with venv activated
✅ Neo4j Aura Free Tier — vector index support confirmed
   (Aura Free supports vector indexes as of Neo4j 5.x)
✅ You have at least 2-3 sample documents to test with
   (PDFs, .docx, or .txt files — SOPs, vendor policies, quality guides)
✅ Anthropic API key available (already in your .env from Step 4)
✅ Note: Claude does NOT have a native embedding model — we use
   sentence-transformers (free, local, no API cost) for embeddings
```

### Confirm your Aura instance supports vector indexes

Run this in the **Aura Query console**
(console.neo4j.io → your instance → Query):

```cypher
CALL dbms.components()
YIELD name, versions
RETURN name, versions;
// Version must be 5.x or higher for vector index support
```

---

## Section 1 — Install Additional Dependencies

```bash
# Activate your existing venv first
source venv/bin/activate     # Mac/Linux
# venv\Scripts\activate      # Windows

# Document loaders
pip install pypdf                    # PDF loading
pip install python-docx              # Word document loading
pip install unstructured             # fallback for complex formats

# Embeddings
# Claude does not have a native embedding model.
# We use sentence-transformers — free, runs locally, no API key needed.
pip install sentence-transformers    # primary embedding model
pip install tiktoken                 # token counting for chunking

# LangChain Anthropic — already installed in Step 4
# langchain-anthropic is already in your venv
```

---

## Section 2 — Update Project Structure

Add new files to your existing `ontology_mock/` project:

```
ontology_mock/
├── .env                          ← add EMBEDDING_MODEL var (Section 3)
├── main.py                       ← add new /ask-with-docs route
├── agent/
│   ├── __init__.py
│   ├── graph_chain.py            ← unchanged from Step 4
│   ├── schema_context.py         ← unchanged from Step 4
│   ├── prompts.py                ← add hybrid prompt (Section 7)
│   ├── rag_chain.py              ← NEW — vector search + hybrid agent
│   └── document_loader.py        ← NEW — ingestion pipeline
├── api/
│   ├── __init__.py
│   └── routes.py                 ← add /ask-with-docs endpoint
├── docs/                         ← NEW — put your documents here
│   ├── vendor_scorecard_sop.pdf
│   ├── procurement_policy.docx
│   ├── quality_standards.pdf
│   └── carrier_sla_guidelines.txt
└── ingest.py                     ← NEW — run once to load all docs
```

Create new files and folders:

```bash
mkdir docs
touch agent/rag_chain.py agent/document_loader.py ingest.py
```

---

## Section 3 — Update `.env` File

Add these lines to your existing `.env`:

```bash
# .env — additions for Step 5

# Embedding model
# Claude has no native embedding model.
# We use sentence-transformers which runs locally — no API key needed.
# all-MiniLM-L6-v2 is fast, lightweight, and well-suited for domain text.
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Anthropic — already set from Step 4, no change needed
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx

# Chunking config
CHUNK_SIZE=500
CHUNK_OVERLAP=75

# Neo4j vector index name
VECTOR_INDEX_NAME=supply_chain_knowledge
VECTOR_DIMENSIONS=384       # all-MiniLM-L6-v2 outputs 384 dimensions

# Path to your documents folder
DOCS_FOLDER=./docs
```

---

## Section 4 — Create the Vector Index in Neo4j Aura

Run this **once** in the Aura Query console before ingesting any documents.

### 4.1 — Create the KnowledgeChunk node constraint

```cypher
// Unique constraint on chunk_id
CREATE CONSTRAINT constraint_chunk_id IF NOT EXISTS
FOR (kc:KnowledgeChunk)
REQUIRE kc.chunk_id IS UNIQUE;
```

### 4.2 — Create the vector index

```cypher
// This is the vector index Neo4j uses for similarity search
// dimension must match your embedding model output:
//   all-MiniLM-L6-v2  → 384  (what we use with Claude)
//
// If you switch embedding models later, drop and recreate this index.

CREATE VECTOR INDEX supply_chain_knowledge IF NOT EXISTS
FOR (kc:KnowledgeChunk)
ON kc.embedding
OPTIONS {
    indexConfig: {
        `vector.dimensions`:    384,
        `vector.similarity_function`: 'cosine'
    }
};
```

```cypher
// Verify the index was created
SHOW VECTOR INDEXES;
// Should show: supply_chain_knowledge | ONLINE | KnowledgeChunk | embedding
```

### 4.3 — Create supporting indexes for metadata filtering

```cypher
// Agents will filter chunks by source document and entity type
CREATE INDEX index_chunk_source IF NOT EXISTS
FOR (kc:KnowledgeChunk) ON (kc.source_file);

CREATE INDEX index_chunk_entity_type IF NOT EXISTS
FOR (kc:KnowledgeChunk) ON (kc.entity_type);

CREATE INDEX index_chunk_doc_type IF NOT EXISTS
FOR (kc:KnowledgeChunk) ON (kc.doc_type);
```

---

## Section 5 — Document Loader Pipeline

```python
# agent/document_loader.py
# Handles loading, chunking, and embedding of all document types.
# Produces a list of chunk dicts ready to be written to Neo4j.

import os
import re
import hashlib
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LangChain document loaders ────────────────────────────────────────────────
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Embedding model ───────────────────────────────────────────────────────────
# Using sentence-transformers (HuggingFace) as the embedding provider.
# Claude (Anthropic) does not have a native embedding model, so we use
# all-MiniLM-L6-v2 — fast, free, runs entirely locally.
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "huggingface")
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE         = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP      = int(os.getenv("CHUNK_OVERLAP", 75))


def get_embedder():
    """
    Returns the HuggingFace sentence-transformers embedding model.
    Call this once and reuse — initialising it per chunk is very slow.
    The model is downloaded automatically on first run (~90MB).
    Subsequent runs use the local cache — no internet needed.
    """
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},   # change to "cuda" if you have a GPU
        encode_kwargs={"normalize_embeddings": True}
    )


def load_document(file_path: str) -> List[Any]:
    """
    Loads a document using the appropriate LangChain loader for its type.
    Returns a list of LangChain Document objects (one per page for PDFs).
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext in [".docx", ".doc"]:
        loader = Docx2txtLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")

    return loader.load()


def infer_doc_metadata(file_path: str) -> Dict[str, str]:
    """
    Infers metadata from the filename to tag chunks for filtering.
    Naming convention: <entity_type>_<doc_type>_<description>.pdf
    Examples:
      vendor_sop_scorecard.pdf          → entity_type=vendor, doc_type=sop
      procurement_policy_2024.pdf       → entity_type=procurement, doc_type=policy
      carrier_sla_guidelines.txt        → entity_type=carrier, doc_type=sla
      quality_standards_global.pdf      → entity_type=quality, doc_type=standards
      plant_maintenance_manual.docx     → entity_type=plant, doc_type=manual
    """
    filename = Path(file_path).stem.lower()
    parts    = filename.split("_")

    # Map first part of filename to graph node entity type
    entity_map = {
        "vendor":        "Vendor",
        "procurement":   "Vendor",
        "supplier":      "Vendor",
        "product":       "Product",
        "sku":           "Product",
        "plant":         "Plant",
        "manufacturing": "Plant",
        "warehouse":     "Warehouse",
        "inventory":     "Warehouse",
        "carrier":       "Carrier",
        "logistics":     "Carrier",
        "shipment":      "Carrier",
        "customer":      "Customer",
        "quality":       "general",
        "general":       "general",
    }

    doc_type_map = {
        "sop":       "Standard Operating Procedure",
        "policy":    "Policy Document",
        "sla":       "Service Level Agreement",
        "manual":    "Operations Manual",
        "standards": "Quality Standards",
        "guide":     "Reference Guide",
        "contract":  "Contract",
        "report":    "Report",
    }

    entity_type = entity_map.get(parts[0] if parts else "", "general")
    doc_type    = doc_type_map.get(parts[1] if len(parts) > 1 else "", "Document")

    return {
        "entity_type": entity_type,
        "doc_type":    doc_type,
        "source_file": Path(file_path).name,
    }


def chunk_and_embed_document(file_path: str, embedder) -> List[Dict]:
    """
    Full pipeline for one document:
      1. Load file → LangChain Documents
      2. Split into chunks
      3. Embed each chunk
      4. Return list of dicts ready for Neo4j ingestion

    Each dict becomes one :KnowledgeChunk node in Neo4j.
    """
    print(f"\n  📄 Processing: {Path(file_path).name}")

    # Step 1 — Load
    documents = load_document(file_path)
    print(f"     Loaded {len(documents)} page(s)")

    # Step 2 — Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size        = CHUNK_SIZE,
        chunk_overlap     = CHUNK_OVERLAP,
        separators        = ["\n\n", "\n", ". ", " ", ""],
        length_function   = len,
    )
    chunks = splitter.split_documents(documents)
    print(f"     Split into {len(chunks)} chunks")

    # Step 3 — Embed all chunks in one batch call (efficient)
    texts      = [chunk.page_content for chunk in chunks]
    embeddings = embedder.embed_documents(texts)
    print(f"     Embedded {len(embeddings)} chunks")

    # Step 4 — Build Neo4j-ready dicts
    metadata = infer_doc_metadata(file_path)
    result   = []

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        # Deterministic chunk_id based on file + position — safe to re-run
        chunk_id = hashlib.md5(
            f"{metadata['source_file']}_{i}_{chunk.page_content[:50]}".encode()
        ).hexdigest()

        # Clean text: collapse whitespace, strip control characters
        clean_text = re.sub(r"\s+", " ", chunk.page_content).strip()

        result.append({
            "chunk_id":    chunk_id,
            "text":        clean_text,
            "embedding":   embedding,
            "source_file": metadata["source_file"],
            "entity_type": metadata["entity_type"],
            "doc_type":    metadata["doc_type"],
            "chunk_index": i,
            "total_chunks": len(chunks),
            "page_number": chunk.metadata.get("page", 0),
            "char_count":  len(clean_text),
        })

    return result


def load_all_documents(docs_folder: str, embedder) -> List[Dict]:
    """
    Scans the docs/ folder and processes every supported file.
    Returns all chunks from all documents as a flat list.
    """
    folder      = Path(docs_folder)
    supported   = {".pdf", ".docx", ".doc", ".txt"}
    all_chunks  = []

    files = [f for f in folder.iterdir() if f.suffix.lower() in supported]
    print(f"\n📂 Found {len(files)} document(s) in {docs_folder}")

    for file_path in files:
        try:
            chunks = chunk_and_embed_document(str(file_path), embedder)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"  ⚠️  Skipped {file_path.name}: {e}")

    print(f"\n✅ Total chunks ready for Neo4j: {len(all_chunks)}")
    return all_chunks
```

---

## Section 6 — Ingestion Script

This script runs **once** to load all documents into Neo4j Aura.
It is separate from the FastAPI app — run it from the terminal.

```python
# ingest.py
# Run from terminal: python ingest.py
# Re-running is safe — uses MERGE on chunk_id to avoid duplicates

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from agent.document_loader import get_embedder, load_all_documents

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
DOCS_FOLDER    = os.getenv("DOCS_FOLDER", "./docs")
BATCH_SIZE     = 50   # smaller batches — embeddings are large lists


# ── Cypher for writing KnowledgeChunk nodes ───────────────────────────────────
# Using MERGE so re-running ingest.py is safe (won't duplicate chunks)

CHUNK_WRITE_CYPHER = """
UNWIND $rows AS row
MERGE (kc:KnowledgeChunk {chunk_id: row.chunk_id})
SET kc.text         = row.text,
    kc.embedding    = row.embedding,
    kc.source_file  = row.source_file,
    kc.entity_type  = row.entity_type,
    kc.doc_type     = row.doc_type,
    kc.chunk_index  = row.chunk_index,
    kc.total_chunks = row.total_chunks,
    kc.page_number  = row.page_number,
    kc.char_count   = row.char_count
"""


# ── Cypher to link chunks to existing graph nodes ─────────────────────────────
# After chunks are written, we link them to matching graph entities
# based on the entity_type metadata tag.
# This creates: (Vendor)-[:HAS_DOCUMENT]->(KnowledgeChunk)

LINK_TO_VENDORS_CYPHER = """
MATCH (kc:KnowledgeChunk)
WHERE kc.entity_type = 'Vendor'
WITH kc
MATCH (v:Vendor)
WHERE NOT EXISTS { (v)-[:HAS_DOCUMENT]->(kc) }
MERGE (v)-[:HAS_DOCUMENT {source_file: kc.source_file}]->(kc)
"""

LINK_TO_PRODUCTS_CYPHER = """
MATCH (kc:KnowledgeChunk)
WHERE kc.entity_type = 'Product'
WITH kc
MATCH (p:Product)
WHERE NOT EXISTS { (p)-[:HAS_DOCUMENT]->(kc) }
MERGE (p)-[:HAS_DOCUMENT {source_file: kc.source_file}]->(kc)
"""

LINK_TO_PLANTS_CYPHER = """
MATCH (kc:KnowledgeChunk)
WHERE kc.entity_type = 'Plant'
WITH kc
MATCH (pl:Plant)
WHERE NOT EXISTS { (pl)-[:HAS_DOCUMENT]->(kc) }
MERGE (pl)-[:HAS_DOCUMENT {source_file: kc.source_file}]->(kc)
"""

LINK_TO_CARRIERS_CYPHER = """
MATCH (kc:KnowledgeChunk)
WHERE kc.entity_type = 'Carrier'
WITH kc
MATCH (ca:Carrier)
WHERE NOT EXISTS { (ca)-[:HAS_DOCUMENT]->(kc) }
MERGE (ca)-[:HAS_DOCUMENT {source_file: kc.source_file}]->(kc)
"""


def write_chunks_to_neo4j(driver, chunks: list):
    """Write chunks in batches to Neo4j."""
    total   = len(chunks)
    written = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i: i + BATCH_SIZE]
        with driver.session(database=NEO4J_DATABASE) as session:
            session.execute_write(lambda tx, b=batch: tx.run(CHUNK_WRITE_CYPHER, {"rows": b}))
        written += len(batch)
        print(f"  Written {written}/{total} chunks to Neo4j")

    print(f"  ✅ All {total} chunks written.")


def link_chunks_to_entities(driver):
    """
    Creates HAS_DOCUMENT relationships between KnowledgeChunks
    and the matching graph entity nodes.
    General-tagged documents are accessible to all entity types via vector search.
    """
    print("\n🔗 Linking document chunks to graph entities...")
    for cypher, label in [
        (LINK_TO_VENDORS_CYPHER,  "Vendor"),
        (LINK_TO_PRODUCTS_CYPHER, "Product"),
        (LINK_TO_PLANTS_CYPHER,   "Plant"),
        (LINK_TO_CARRIERS_CYPHER, "Carrier"),
    ]:
        with driver.session(database=NEO4J_DATABASE) as session:
            session.execute_write(lambda tx, c=cypher: tx.run(c))
        print(f"  ✅ Linked to {label} nodes")


def verify_ingestion(driver):
    """Print a summary of what was ingested."""
    print("\n📊 Ingestion summary:")
    with driver.session(database=NEO4J_DATABASE) as session:

        # Count chunks by entity type
        result = session.run("""
            MATCH (kc:KnowledgeChunk)
            RETURN kc.entity_type AS entity_type,
                   kc.doc_type    AS doc_type,
                   count(kc)      AS chunk_count,
                   collect(DISTINCT kc.source_file)[0..3] AS sample_files
            ORDER BY chunk_count DESC
        """)
        print(f"\n  {'Entity Type':<20} {'Doc Type':<30} {'Chunks':<10} Sample Files")
        print(f"  {'-'*80}")
        for row in result:
            print(f"  {row['entity_type']:<20} {row['doc_type']:<30} "
                  f"{row['chunk_count']:<10} {row['sample_files']}")

        # Count HAS_DOCUMENT relationships
        rel_result = session.run("""
            MATCH ()-[r:HAS_DOCUMENT]->()
            RETURN count(r) AS total_links
        """)
        total_links = rel_result.single()["total_links"]
        print(f"\n  Total HAS_DOCUMENT relationships created: {total_links}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("CPG Supply Chain — Knowledge Base Ingestion")
    print("=" * 60)

    # 1. Load and embed all documents
    print("\n📥 Step 1: Loading and embedding documents...")
    embedder   = get_embedder()
    all_chunks = load_all_documents(DOCS_FOLDER, embedder)

    if not all_chunks:
        print("⚠️  No chunks produced. Check your docs/ folder has PDF/DOCX/TXT files.")
        exit(1)

    # 2. Write to Neo4j
    print("\n📤 Step 2: Writing chunks to Neo4j Aura...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        write_chunks_to_neo4j(driver, all_chunks)
        link_chunks_to_entities(driver)
        verify_ingestion(driver)
    finally:
        driver.close()

    print("\n✅ Ingestion complete. Knowledge base is ready.")
    print("   You can now use the /api/v1/ask-with-docs endpoint.")
```

**Run the ingestion:**

```bash
# Put your PDF/DOCX/TXT files in the docs/ folder first
python ingest.py
```

---

## Section 7 — Update Prompts for Hybrid Mode

Add the hybrid prompt to your existing `agent/prompts.py`:

```python
# agent/prompts.py — ADD this block to the existing file

HYBRID_ANSWER_PROMPT = """
You are a CPG supply chain analyst with access to both live supply chain
data from a knowledge graph AND institutional documents from a knowledge base.

The user asked: {question}

## STRUCTURED DATA (from the knowledge graph — live supply chain metrics):
{graph_results}

## DOCUMENT CONTEXT (from knowledge base — policies, SOPs, guidelines):
{doc_results}

## YOUR JOB
Write a comprehensive answer that combines BOTH sources:
1. Use the structured data for specific numbers, names, and current status
2. Use the document context for policy guidance, recommended actions, and best practices
3. Clearly distinguish when you are citing live data vs. policy/guidance
4. If one source is empty, answer from the other source only
5. Be specific — use actual names and numbers from the data
6. Keep the answer under 300 words unless complexity requires more
7. Format with bullet points for recommendations
8. Never invent information not present in either source

Answer:
"""

# Also add this to the prompts.py file —
# used when we only have document results (no graph match):
DOC_ONLY_ANSWER_PROMPT = """
You are a CPG supply chain analyst.

The user asked: {question}

No matching structured data was found in the knowledge graph.
However, the following document context was retrieved:

{doc_results}

Answer the question using ONLY the document context above.
If the documents don't answer the question either, say so clearly.
Keep the answer concise and grounded in the retrieved text.

Answer:
"""
```

---

## Section 8 — The RAG Chain (Vector Search + Hybrid Agent)

```python
# agent/rag_chain.py
# Handles vector similarity search and the hybrid graph+document pipeline.

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI        = os.getenv("NEO4J_URI")
NEO4J_USER       = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD   = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE   = "neo4j"
VECTOR_INDEX     = os.getenv("VECTOR_INDEX_NAME", "supply_chain_knowledge")
TOP_K_CHUNKS     = 5     # number of document chunks to retrieve per query


# ── Embedding ─────────────────────────────────────────────────────────────────

def get_embedder():
    """Reuse the same HuggingFace embedder from document_loader.py."""
    from agent.document_loader import get_embedder as _get_embedder
    return _get_embedder()


# ── Vector similarity search ──────────────────────────────────────────────────

def vector_search(question: str, top_k: int = TOP_K_CHUNKS,
                  entity_type_filter: str = None) -> List[Dict]:
    """
    Embeds the question and finds the most semantically similar
    KnowledgeChunk nodes using Neo4j's vector index.

    entity_type_filter: optionally restrict to chunks from a specific
    entity type — e.g. 'Vendor' when the question is clearly about vendors.
    """
    embedder        = get_embedder()
    question_vector = embedder.embed_query(question)

    # Build Cypher — filter by entity_type if provided
    if entity_type_filter and entity_type_filter != "general":
        cypher = """
        CALL db.index.vector.queryNodes(
            $index_name,
            $top_k,
            $embedding
        ) YIELD node AS kc, score
        WHERE kc.entity_type IN [$entity_type, 'general']
        RETURN kc.chunk_id    AS chunk_id,
               kc.text        AS text,
               kc.source_file AS source_file,
               kc.doc_type    AS doc_type,
               kc.entity_type AS entity_type,
               kc.page_number AS page_number,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """
        params = {
            "index_name":  VECTOR_INDEX,
            "top_k":       top_k,
            "embedding":   question_vector,
            "entity_type": entity_type_filter,
        }
    else:
        cypher = """
        CALL db.index.vector.queryNodes(
            $index_name,
            $top_k,
            $embedding
        ) YIELD node AS kc, score
        RETURN kc.chunk_id    AS chunk_id,
               kc.text        AS text,
               kc.source_file AS source_file,
               kc.doc_type    AS doc_type,
               kc.entity_type AS entity_type,
               kc.page_number AS page_number,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """
        params = {
            "index_name": VECTOR_INDEX,
            "top_k":      top_k,
            "embedding":  question_vector,
        }

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(cypher, params)
            return [dict(row) for row in result]
    finally:
        driver.close()


def format_doc_results(chunks: List[Dict]) -> str:
    """
    Formats retrieved document chunks into a clean string
    for the LLM context window.
    """
    if not chunks:
        return "No relevant documents found."

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        score = round(chunk.get("score", 0), 3)
        formatted.append(
            f"[{i}] Source: {chunk['source_file']} "
            f"(Type: {chunk['doc_type']}, Page: {chunk.get('page_number', 'N/A')}, "
            f"Relevance: {score})\n"
            f"{chunk['text']}\n"
        )
    return "\n---\n".join(formatted)


# ── Entity type inference ─────────────────────────────────────────────────────

def infer_entity_type_from_question(question: str) -> str:
    """
    Simple keyword-based classifier to infer which entity type
    the question is most about. Used to filter vector search results.
    Not perfect — falls back to no filter if ambiguous.
    """
    q = question.lower()

    if any(w in q for w in ["vendor", "supplier", "procurement", "purchase order",
                              "lead time", "under-delivery", "rebalance supply"]):
        return "Vendor"
    elif any(w in q for w in ["plant", "manufacturing", "production", "machine",
                               "defect", "downtime", "throughput", "shift"]):
        return "Plant"
    elif any(w in q for w in ["carrier", "shipment", "freight", "transit",
                               "logistics", "delivery", "route"]):
        return "Carrier"
    elif any(w in q for w in ["product", "sku", "category", "brand", "stockout",
                               "inventory", "warehouse", "stock"]):
        return "Product"
    elif any(w in q for w in ["customer", "fulfillment", "demand", "order",
                               "revenue", "retail"]):
        return "Customer"
    else:
        return "general"   # no filter — search all chunks


# ── Hybrid agent ──────────────────────────────────────────────────────────────

def run_hybrid_agent(question: str) -> Dict[str, Any]:
    """
    Full hybrid pipeline:
      1. Run the graph agent (Step 4 chain) for structured data
      2. Run vector search for relevant document chunks
      3. Synthesize both into a single answer

    Returns a dict with all intermediate results for transparency.
    """
    from agent.graph_chain import run_supply_chain_agent, get_llm
    # get_llm() returns ChatAnthropic (Claude) as configured in graph_chain.py
    from agent.prompts import HYBRID_ANSWER_PROMPT, DOC_ONLY_ANSWER_PROMPT

    # ── Step 1: Graph query (reuse Step 4 agent) ──────────────────────────────
    print(f"\n  [1/3] Running graph query...")
    graph_result = run_supply_chain_agent(question)
    graph_rows   = graph_result.get("raw_results", [])
    graph_text   = "\n".join([str(r) for r in graph_rows[:50]]) if graph_rows else ""
    cypher_query = graph_result.get("cypher_query", "")

    # ── Step 2: Vector search ─────────────────────────────────────────────────
    print(f"  [2/3] Running vector search...")
    entity_type  = infer_entity_type_from_question(question)
    doc_chunks   = vector_search(question, top_k=TOP_K_CHUNKS,
                                 entity_type_filter=entity_type)
    doc_text     = format_doc_results(doc_chunks)

    # ── Step 3: Hybrid LLM synthesis ─────────────────────────────────────────
    print(f"  [3/3] Synthesising answer...")
    llm = get_llm()

    # Choose prompt based on what data is available
    if graph_text and doc_text != "No relevant documents found.":
        # Both sources available — full hybrid answer
        prompt   = PromptTemplate(
            input_variables=["question", "graph_results", "doc_results"],
            template=HYBRID_ANSWER_PROMPT
        )
        chain    = prompt | llm | StrOutputParser()
        answer   = chain.invoke({
            "question":     question,
            "graph_results": graph_text,
            "doc_results":   doc_text,
        })
        answer_source = "hybrid"

    elif graph_text:
        # Only graph data — use Step 4 answer (already generated)
        answer        = graph_result.get("answer", "No answer generated.")
        answer_source = "graph_only"

    elif doc_text != "No relevant documents found.":
        # Only documents — use doc-only prompt
        prompt   = PromptTemplate(
            input_variables=["question", "doc_results"],
            template=DOC_ONLY_ANSWER_PROMPT
        )
        chain    = prompt | llm | StrOutputParser()
        answer   = chain.invoke({
            "question":   question,
            "doc_results": doc_text,
        })
        answer_source = "docs_only"

    else:
        answer        = ("No matching data found in the knowledge graph or "
                         "document knowledge base. Please rephrase your question.")
        answer_source = "no_results"

    return {
        "question":       question,
        "answer":         answer,
        "answer_source":  answer_source,   # hybrid / graph_only / docs_only / no_results
        "cypher_query":   cypher_query,
        "graph_results":  graph_rows,
        "doc_chunks":     doc_chunks,
        "entity_type":    entity_type,
        "status":         "success" if answer_source != "no_results" else "no_results"
    }
```

---

## Section 9 — Add New API Endpoint

Add this to your existing `api/routes.py`:

```python
# api/routes.py — ADD these blocks to the existing file

from agent.rag_chain import run_hybrid_agent   # add to imports at top

# ── New request/response models ───────────────────────────────────────────────

class HybridQuestionRequest(BaseModel):
    question:          str
    show_cypher:       Optional[bool] = False
    show_doc_sources:  Optional[bool] = False   # show which documents were used


class HybridAgentResponse(BaseModel):
    question:         str
    answer:           str
    answer_source:    str    # hybrid / graph_only / docs_only / no_results
    status:           str
    cypher_query:     Optional[str]        = None
    doc_sources:      Optional[List[str]]  = None
    graph_result_count: Optional[int]      = None
    doc_chunk_count:    Optional[int]      = None


# ── New endpoint ──────────────────────────────────────────────────────────────

@router.post("/ask-with-docs", response_model=HybridAgentResponse)
async def ask_with_docs(request: HybridQuestionRequest):
    """
    Hybrid chatbox endpoint — combines graph data AND document knowledge base.
    POST { "question": "How should I rebalance vendor supply per our procurement policy?" }
    Returns an answer grounded in both live graph data and your SOP documents.
    """
    if not request.question or len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="Question is too short.")

    result = run_hybrid_agent(request.question.strip())

    # Extract document source file names for transparency
    doc_sources = None
    if request.show_doc_sources and result.get("doc_chunks"):
        doc_sources = list({
            c["source_file"] for c in result["doc_chunks"]
        })

    return HybridAgentResponse(
        question           = result["question"],
        answer             = result["answer"],
        answer_source      = result["answer_source"],
        status             = result["status"],
        cypher_query       = result["cypher_query"] if request.show_cypher else None,
        doc_sources        = doc_sources,
        graph_result_count = len(result.get("graph_results") or []),
        doc_chunk_count    = len(result.get("doc_chunks") or []),
    )


@router.get("/knowledge-base/stats")
async def knowledge_base_stats():
    """
    Returns stats about what's in the document knowledge base.
    Useful for confirming ingestion worked correctly.
    """
    from neo4j import GraphDatabase
    import os

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )
    try:
        with driver.session(database="neo4j") as session:
            result = session.run("""
                MATCH (kc:KnowledgeChunk)
                RETURN kc.entity_type  AS entity_type,
                       count(kc)       AS chunk_count,
                       collect(DISTINCT kc.source_file) AS files
                ORDER BY chunk_count DESC
            """)
            rows = [dict(r) for r in result]

            total = session.run(
                "MATCH (kc:KnowledgeChunk) RETURN count(kc) AS total"
            ).single()["total"]

        return {"total_chunks": total, "breakdown": rows}
    finally:
        driver.close()
```

---

## Section 10 — Test the Full Hybrid Pipeline

### 10.1 — Run ingestion first

```bash
# Put at least 2-3 documents in docs/ folder
# Then run:
python ingest.py
```

Expected output:
```
============================================================
CPG Supply Chain — Knowledge Base Ingestion
============================================================

📂 Found 3 document(s) in ./docs

  📄 Processing: vendor_scorecard_sop.pdf
     Loaded 8 page(s)
     Split into 42 chunks
     Embedded 42 chunks

  📄 Processing: procurement_policy.docx
     ...

✅ Total chunks ready for Neo4j: 128

📤 Step 2: Writing chunks to Neo4j Aura...
  Written 50/128 chunks to Neo4j
  Written 100/128 chunks to Neo4j
  Written 128/128 chunks to Neo4j
  ✅ All 128 chunks written.

🔗 Linking document chunks to graph entities...
  ✅ Linked to Vendor nodes
  ...

✅ Ingestion complete. Knowledge base is ready.
```

### 10.2 — Verify in Aura console

```cypher
// Confirm KnowledgeChunk nodes exist with embeddings
MATCH (kc:KnowledgeChunk)
RETURN kc.source_file,
       kc.entity_type,
       kc.doc_type,
       kc.chunk_index,
       left(kc.text, 80) AS text_preview,
       size(kc.embedding) AS embedding_dimensions
LIMIT 10;
```

```cypher
// Confirm HAS_DOCUMENT links were created
MATCH (v:Vendor)-[:HAS_DOCUMENT]->(kc:KnowledgeChunk)
RETURN v.vendor_name, kc.source_file, left(kc.text, 60) AS preview
LIMIT 5;
```

### 10.3 — Test hybrid endpoint

```bash
# Restart the server first to pick up new routes
uvicorn app_main:app_main --reload --port 8000

# Test a question that benefits from both graph + documents
curl -X POST http://localhost:8000/api/v1/ask-with-docs \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How should I rebalance vendor supply for at-risk suppliers?",
    "show_cypher": true,
    "show_doc_sources": true
  }'
```

### 10.4 — Full hybrid test suite

```python
# test_hybrid.py

import requests

BASE_URL = "http://localhost:8000/api/v1"

hybrid_questions = [
    # These benefit most from hybrid — graph data + policy guidance combined
    "How should I rebalance vendor supply for at-risk suppliers?",
    "What is the recommended action when a warehouse is in stockout?",
    "Which vendors are critical and what does our procurement policy say about them?",
    "How do I improve machine utilization for underperforming plants?",
    "What are our SLA requirements for carriers that are underperforming?",

    # These are graph-heavy — doc context is supplementary
    "Which vendors have the highest risk scores?",
    "Show me products with compounded supply risk",

    # These are doc-heavy — graph provides names, docs provide guidance
    "What is our vendor scorecard methodology?",
    "What quality standards apply to our manufacturing plants?",
]

for question in hybrid_questions:
    print(f"\n{'='*65}")
    print(f"Q: {question}")

    r    = requests.post(f"{BASE_URL}/ask-with-docs",
                         json={"question": question,
                               "show_cypher": True,
                               "show_doc_sources": True})
    data = r.json()

    print(f"SOURCE:  {data['answer_source']}")
    print(f"GRAPHS:  {data['graph_result_count']} rows  |  "
          f"DOCS: {data['doc_chunk_count']} chunks")
    if data.get("doc_sources"):
        print(f"DOC FILES: {', '.join(data['doc_sources'])}")
    print(f"ANSWER:\n{data['answer']}")
```

---

## Section 11 — Update the Chatbox UI

Add a second toggle in `chatbox.html` to switch between graph-only and hybrid mode:

```html
<!-- Add inside the .suggestions div in chatbox.html -->
<div style="padding: 8px 16px; display:flex; align-items:center; gap:10px;
            border-bottom: 1px solid #e5e7eb; background: #fafafa;">
  <span style="font-size:12px; color:#6b7280;">Mode:</span>
  <label style="font-size:12px; cursor:pointer;">
    <input type="radio" name="mode" value="ask" checked
           onchange="setMode(this.value)">
    Graph only
  </label>
  <label style="font-size:12px; cursor:pointer;">
    <input type="radio" name="mode" value="ask-with-docs"
           onchange="setMode(this.value)">
    Graph + Documents (GraphRAG)
  </label>
</div>

<script>
  // Add this to the existing <script> block in chatbox.html
  let currentMode = "ask";   // "ask" or "ask-with-docs"

  function setMode(mode) {
    currentMode = mode;
  }

  // Update sendQuestion() to use currentMode:
  // Change:  const res = await fetch(`${BASE_URL}/ask`, ...
  // To:      const res = await fetch(`${BASE_URL}/${currentMode}`, ...
  // and for ask-with-docs add: show_doc_sources: true to the body
</script>
```

---

## Section 12 — Verify the Complete Step 5 Setup

```
✅ python ingest.py completes without errors
✅ KnowledgeChunk nodes visible in Aura Query console
✅ SHOW VECTOR INDEXES shows supply_chain_knowledge as ONLINE
✅ /api/v1/knowledge-base/stats returns correct chunk counts
✅ /api/v1/ask-with-docs returns answer_source: "hybrid" for policy questions
✅ show_doc_sources returns actual filenames from your docs/ folder
✅ chatbox.html mode toggle switches between graph-only and GraphRAG
```

---

## Summary: What You Have After Step 5

```
KNOWLEDGE BASE:
  KnowledgeChunk nodes in Neo4j Aura with:
    - text          (cleaned document chunk)
    - embedding     (float vector for similarity search)
    - source_file   (original document filename)
    - entity_type   (Vendor / Plant / Carrier / Product / general)
    - doc_type      (SOP / Policy / Manual / SLA / etc.)
  Linked to graph entities via HAS_DOCUMENT relationships

VECTOR INDEX:
  supply_chain_knowledge (cosine similarity, 384 dimensions, online)
  Embedding model: all-MiniLM-L6-v2 (local, free, no API cost)

NEW ENDPOINTS:
  POST /api/v1/ask-with-docs    ← hybrid graph + document agent
  GET  /api/v1/knowledge-base/stats ← ingestion health check

HYBRID AGENT PIPELINE:
  Question
    → Graph Cypher query (structured supply chain data)
    → Vector similarity search (document chunks)
    → LLM synthesises both into one grounded answer
    → answer_source field tells you which sources contributed

ANSWER TYPES:
  hybrid      → both graph data and documents contributed
  graph_only  → only graph data matched
  docs_only   → only documents matched
  no_results  → neither matched (graceful fallback)

FULL GRAPHRAG STACK:
  Databricks Delta Tables        ← source of truth (Steps 1-2)
  Neo4j Aura Graph               ← enriched knowledge graph (Step 3)
  Claude (Anthropic)             ← LLM for Cypher generation + answers
  sentence-transformers (local)  ← embeddings (no API cost)
  FastAPI Agent                  ← graph-only chatbox (Step 4)
  Neo4j Vector Index             ← document knowledge base (Step 5)
  Hybrid FastAPI Agent           ← GraphRAG chatbox (Step 5)
```
