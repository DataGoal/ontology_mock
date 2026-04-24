# CPG Supply Chain Knowledge Graph — Implementation Guide

This directory contains the step-by-step guides for converting the generated
star-schema data into an enriched, AI-ready knowledge graph in Neo4j.

## Architecture Overview

```
Databricks Delta Tables          Neo4j Knowledge Graph
(star schema data)          →    (enriched property graph)
         ↓                                ↓
   Data Generator              AI Agents + ChatBox + Bloom UI
```

---

## Running the AI Agent Service

### Prerequisites

- Python 3.10+
- Neo4j Aura instance populated through Steps 1–3
- Anthropic API key

### Step 1 — Install AI service dependencies

The root `requirements.txt` covers the data generator only. Install the
full AI service stack separately:

```bash
cd ontology_mock
python -m venv venv
source venv/bin/activate        # Mac / Linux
# venv\Scripts\activate         # Windows

pip install \
  fastapi uvicorn[standard] python-dotenv \
  langchain langchain-anthropic langchain-community langchain-text-splitters \
  neo4j \
  sentence-transformers \
  pypdf docx2txt \
  pydantic
```

### Step 2 — Configure credentials

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```ini
# Neo4j Aura
NEO4J_URI=neo4j+s://<your-aura-id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-password>
NEO4J_DATABASE=neo4j

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Vector index (used by GraphRAG / Step 5)
VECTOR_INDEX_NAME=supply_chain_knowledge
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Step 3 — Start the FastAPI server

```bash
uvicorn app_main:app_main --reload --port 8000
```

Expected output:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

---

### Swagger UI

Open **`http://localhost:8000/docs`** in your browser to get the full
interactive API explorer.

All endpoints are grouped under `/api/v1`:

| Group | Endpoint | Method | Description |
|-------|----------|--------|-------------|
| Graph query | `/api/v1/ask` | POST | Natural language → Cypher → answer |
| Graph + Docs | `/api/v1/ask-with-docs` | POST | GraphRAG: graph + vector document search |
| Anomaly | `/api/v1/anomaly/detect` | POST | Full anomaly sweep (all types) |
| Anomaly | `/api/v1/anomaly/detect/critical` | POST | CRITICAL severity only (fast shortcut) |
| Anomaly | `/api/v1/anomaly/types` | GET | List all registered anomaly types |
| Pipeline | `/api/v1/pipeline/run` | POST | Full 4-agent pipeline: Detect → Root Cause → Impact → Recommend |
| Pipeline | `/api/v1/anomaly/{id}/root-cause` | POST | Root cause analysis for one signal |
| Pipeline | `/api/v1/anomaly/{id}/impact` | POST | Downstream impact analysis for one signal |
| Pipeline | `/api/v1/anomaly/{id}/recommend` | POST | Recommendations for one signal |
| Knowledge base | `/api/v1/knowledge-base/stats` | GET | Document chunk stats from vector index |
| Utility | `/api/v1/health` | GET | Service health check |
| Utility | `/api/v1/sample-questions` | GET | Example questions by category |

**Try it in Swagger:**

1. Click any endpoint to expand it.
2. Click **Try it out**.
3. Edit the request body (pre-filled with defaults).
4. Click **Execute** — the response appears immediately below.

Quick smoke test — paste this into `/api/v1/ask`:
```json
{
  "question": "Which vendors are at high risk right now?",
  "show_cypher": true
}
```

---

### Chatbox (browser UI)

Open **`tests/chat.html`** directly in your browser — no additional server
needed. The file calls the FastAPI server at `http://localhost:8000/api/v1/ask`
so the server must already be running.

**Interface features:**

| Feature | How to use |
|---------|------------|
| Ask a question | Type in the input bar and press **Enter** or click **Ask** |
| Quick suggestions | Click any chip at the top to pre-fill and send a sample question |
| Show Cypher | Each answer includes a **Show generated Cypher ↓** link that reveals the query the LLM produced |
| Graph only mode | Default — queries the knowledge graph directly |
| GraphRAG mode | Switch to **Graph + Documents** to combine graph data with ingested SOP documents |

**Sample questions to try:**

```
Which vendors are at high risk right now?
Which warehouses have stockouts?
Which plants are over capacity?
Show me actionable vendor alternatives
Which VIP customers are at risk?
```

---

## Implementation Path

Follow the steps in order. Each step builds on the output of the previous one.

### Foundation (Required)

| Step | File | What it covers | Prerequisites |
|------|------|----------------|---------------|
| 1 | [step1_ontology_neo4j_guide.md](step1_ontology_neo4j_guide.md) | Define constraints, indexes, and ontology schema in Neo4j Desktop. Set up node labels and relationship types. | Neo4j Desktop installed |
| 2 | [step2_databricks_to_neo4j.md](step2_databricks_to_neo4j.md) | ETL pipeline: load Delta table dimension rows as graph nodes, then aggregate fact table metrics as relationship properties. | Step 1 complete; Databricks cluster running |
| 3 | [step3_graph_enrichment.md](step3_graph_enrichment.md) | Compute risk flags, composite scores, centrality signals, and health indicators directly in Cypher. This is what AI agents reason over. | Step 2 complete; APOC plugin installed |

### AI Agent Layer (Builds on Step 3)

| Step | File | What it covers | Prerequisites |
|------|------|----------------|---------------|
| 4 | [step4_ai_agent_integration.md](step4_ai_agent_integration.md) | Wire LangChain to Neo4j Aura. Build a FastAPI chatbox where users type natural language questions and receive Cypher-grounded answers. | Step 3 complete; Python environment |
| 5 | [step5_graphrag_knowledge_base.md](step5_graphrag_knowledge_base.md) | Ingest unstructured documents (PDFs, SOPs, contracts), embed them as vector nodes in Neo4j, and upgrade the Step 4 agent to a hybrid GraphRAG agent. | Step 4 complete; vector index support |

### Multi-Agent Pipeline (Builds on Step 4)

| Step | File | What it covers | Prerequisites |
|------|------|----------------|---------------|
| 6A | [step6a_anomaly_detection_agent.md](step6a_anomaly_detection_agent.md) | Anomaly Detection Agent: threshold-based Cypher queries detect abnormal patterns across all entity types. Emits structured `AnomalySignal` objects. LLM writes narrative summaries only. | Step 4 complete |
| 6B–6D | [step6_agents.md](step6_agents.md) | Root Cause Agent (upstream traversal), Impact Analysis Agent (downstream traversal), and Recommendation Agent (graph heuristics). Run downstream of Step 6A. | Step 6A complete |

### Visualization

| Step | File | What it covers | Prerequisites |
|------|------|----------------|---------------|
| 9 | [step9_neo4j_bloom_visualization.md](step9_neo4j_bloom_visualization.md) | Five curated Neo4j Bloom Perspectives for visual graph exploration: risk monitoring, inventory health, manufacturing performance, supply chain paths, and anomaly investigation. | Step 3 complete; Neo4j Aura |

---

## Key Concepts

| Concept | Databricks equivalent | Neo4j equivalent |
|---|---|---|
| Table | — | Node Label (e.g., `Vendor`, `Product`) |
| Row | — | Node instance |
| Foreign Key join | — | Relationship (e.g., `-[:SUPPLIES]->`) |
| Fact table metric | Column | Property on a Relationship |
| Schema / DDL | `CREATE TABLE` | Constraint + Index |

In a property graph, **relationships are first-class citizens** — not joins
computed at query time. Fact table metrics become relationship properties
because the measurement belongs to the *connection*, not either entity alone.

---

## Relationship Map (After Step 2)

```
(Vendor)    -[:SUPPLIES]->       (Product)
(Plant)     -[:PRODUCES]->       (Product)
(Warehouse) -[:STOCKS]->         (Product)
(Warehouse) -[:SHIPS_TO]->       (Destination)
(Carrier)   -[:HANDLES_ROUTE]->  (Destination)
(Customer)  -[:DEMANDS]->        (Product)
(Customer)  -[:ORDERS_TO]->      (Destination)
(Vendor)    -[:ALTERNATIVE_FOR]> (Vendor)       ← computed, no source table
```
