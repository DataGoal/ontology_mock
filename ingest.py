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