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
