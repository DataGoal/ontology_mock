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