# agent/rag_chain.py
# Handles vector similarity search and the hybrid graph+document pipeline.

import os
from typing import List, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agent.config import NEO4J_DATABASE, get_driver

VECTOR_INDEX = os.getenv("VECTOR_INDEX_NAME", "supply_chain_knowledge")
TOP_K_CHUNKS = 5


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

    driver = get_driver()
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