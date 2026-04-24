# CPG Supply Chain Data Generator

> **Domain:** Consumer Packaged Goods (modelled after Kimberly-Clark / P&G style supply chains)
> **Purpose:** Generate realistic, relationship-consistent mock data for a dimensional supply chain data model

---

## Project Overview

This project generates production-quality mock data for a CPG supply chain dimensional model (star schema). It covers the full supply chain lifecycle — from vendor procurement through manufacturing, inventory, logistics, and customer demand — using statistically grounded distributions and realistic CPG reference data (brands, products, vendors, plants, warehouses, carriers).

The generated data is suitable for:
- BI/analytics development and testing
- Data engineering pipeline validation
- Semantic layer / ontology development
- ML model training and prototyping
- Data quality tooling evaluation

---

## Project Structure

This project has two layers: a **mock data generator** (Part 1) and an **AI agent service** (Parts 2–6) built on top of the generated Neo4j knowledge graph.

```
ontology_mock/
│
├── ── Part 1: Mock Data Generator ──────────────────────────────────────────
│
├── configs/                          # YAML configuration files
│   ├── schema.yaml                   # Table schemas with column types and constraints
│   ├── data_volumes.yaml             # Row counts by profile (dev/staging/prod)
│   ├── distributions.yaml            # Statistical distributions per field
│   └── relationships.yaml            # FK strategies, business rules, generation order
│
├── src/                              # Core generation logic
│   ├── generators/
│   │   ├── base_generator.py         # Abstract base class + shared sampling utilities
│   │   ├── dim_generators.py         # 9 dimension table generators
│   │   └── fact_generators.py        # 5 fact table generators
│   ├── pipeline.py                   # Orchestration: generate → validate → write
│   └── writer.py                     # CSV / Parquet / JSON output (local + Databricks)
│
├── utils/                            # Shared helpers
│   ├── cpg_reference_data.py         # CPG brand/product/vendor/plant master lists
│   ├── validators.py                 # Schema, RI, and business rule validators
│   └── logger.py                     # Structured logging
│
├── sql/
│   ├── ddl/
│   │   ├── 01_dim_tables.sql         # Databricks Delta DDL for all dimension tables
│   │   ├── 02_fact_tables.sql        # Databricks Delta DDL for all fact tables
│   │   └── 03_views_and_semantic_layer.sql  # Enriched views + supply chain scorecard
│   ├── queries/
│   │   └── sample_analytics.sql      # 8 sample analytics queries (vendor, OTIF, OEE…)
│   └── metric_views/                 # YAML metric view definitions per fact table
│
├── main.py                           # CLI entry point: python main.py --profile dev
├── databricks_main.py                # Databricks notebook entry point
│
├── ── Part 2–6: AI Agent Service ───────────────────────────────────────────
│
├── agent/                            # LangChain + Neo4j agent modules
│   ├── config.py                     # Shared Neo4j connection + LLM factory
│   ├── graph_chain.py                # Graph query agent: NL → Cypher → answer
│   ├── rag_chain.py                  # Hybrid agent: graph + vector document search
│   ├── anomaly_agent.py              # Anomaly detection (threshold-based Cypher queries)
│   ├── root_cause_agent.py           # Upstream graph traversal + weighted scoring
│   ├── impact_agent.py               # Downstream impact analysis
│   ├── recommendation_agent.py       # Ranked action recommendations
│   ├── anomaly_queries.py            # Cypher query registry for all anomaly types
│   ├── document_loader.py            # PDF/text ingestion + HuggingFace embeddings
│   ├── schema_context.py             # Graph schema string injected into Cypher prompts
│   └── prompts.py                    # All LLM prompt templates
│
├── api/                              # FastAPI REST layer
│   └── routes.py                     # All endpoints: /ask, /anomaly, /pipeline, /knowledge-base
│
├── models/                           # Pydantic v2 output models
│   ├── anomaly.py                    # AnomalySignal, ANOMALY_TYPE_REGISTRY
│   ├── root_cause.py                 # RootCauseReport, RootCauseNode
│   ├── impact.py                     # ImpactReport, ImpactedCustomer, ImpactedProduct
│   └── recommendation.py             # RecommendationSet, Recommendation
│
├── docs/                             # Knowledge base documents (PDFs ingested via ingest.py)
├── app_main.py                       # FastAPI entry point: uvicorn app_main:app_main
├── pipeline.py                       # Orchestrates all 4 agents end-to-end
├── ingest.py                         # Loads docs/ into Neo4j KnowledgeChunk vector index
│
├── readme/                           # Step-by-step implementation guides
│   ├── README.md                     # Guide index with links, order and prerequisites
│   ├── step1_ontology_neo4j_guide.md # Define ontology schema in Neo4j Desktop
│   ├── step2_databricks_to_neo4j.md  # ETL: load Delta tables into Neo4j
│   ├── step3_graph_enrichment.md     # Graph enrichment: risk signals & centrality
│   ├── step4_ai_agent_integration.md # LangChain + Neo4j chatbox
│   ├── step5_graphrag_knowledge_base.md # GraphRAG: graph + vector hybrid agent
│   ├── step6a_anomaly_detection_agent.md # Anomaly Detection Agent
│   ├── step6_agents.md               # Root Cause, Impact Analysis & Recommendation Agents
│   └── step9_neo4j_bloom_visualization.md # Neo4j Bloom visual perspectives
│
├── output/                           # Generated data files (git-ignored)
├── requirements.txt
└── README.md
```

---

## Data Model

### Dimension Tables (9)

| Table | Description | Key Columns |
|---|---|---|
| `dim_date` | Calendar date spine | full_date, year, quarter, month, is_holiday |
| `dim_vendor` | Supplier master | vendor_name, tier, reliability_score, avg_lead_time_days |
| `dim_plant` | Manufacturing plants | plant_code, plant_type, capacity_units_per_day |
| `dim_shift` | Work shifts | shift_name, shift_start, shift_end |
| `dim_warehouse` | Distribution centres | warehouse_code, type, storage_capacity_units |
| `dim_carrier` | Logistics carriers | carrier_type, avg_transit_days, on_time_delivery_pct |
| `dim_product` | SKU master | sku, category, sub_category, brand |
| `dim_customer` | Customer accounts | customer_segment, channel |
| `dim_destination` | Delivery destinations | destination_type, lat, lon |

### Fact Tables (5)

| Table | Grain | Key Metrics |
|---|---|---|
| `fact_procurement` | PO line | quantity_ordered, quantity_delivered, total_cost, lead_time_days |
| `fact_manufacturing` | Production run × shift | units_planned/produced, defect_rate_pct, machine_utilization_pct |
| `fact_inventory` | Warehouse × SKU × date | stock_on_hand, reorder_point, safety_stock, stockout/overstock flags |
| `fact_shipment` | Shipment × product | transit_days, delivery_variance_days, freight_cost, OTIF |
| `fact_sales_demand` | Customer order | units_demanded/fulfilled, fulfillment_rate_pct, revenue |

---

## Quick Start

### 1. Install dependencies

```bash
cd ontology_mock
pip install -r requirements.txt
cp .env.example .env   # fill in your Neo4j and Anthropic credentials
```

### 2. Generate mock data

```bash
# Generate dev-scale data (~4,300 rows) as CSV files in output/
python main.py --profile dev --format csv

# Generate staging-scale data and write to Databricks Delta
python main.py --profile staging --format delta --target databricks
```

### 3. Run on Databricks

Open `databricks_main.py` as a notebook in Databricks Repos.  Set the
widgets (`profile`, `catalog`, `db_schema`) and run all cells.  Output
is written as Delta tables.

### 4. Use as a Python library

```python
from src.pipeline import CPGDataPipeline

pipeline = CPGDataPipeline(configs_dir="configs", output_dir="output")
results  = pipeline.run(write=True, validate=True)

# Access individual DataFrames
dim_product_df      = results["dim_product"]
fact_sales_df       = results["fact_sales_demand"]
fact_inventory_df   = results["fact_inventory"]
```

---

## Configuration Reference

### Profiles (`configs/data_volumes.yaml`)

| Profile | Date Range | Total Rows (approx.) | Use Case |
|---|---|---|---|
| `dev` | 1 year | ~4,300 | Local development, unit tests |
| `staging` | 2 years | ~47,000 | Integration testing, QA |
| `prod` | 5 years | ~1,400,000 | Full-scale analytics, ML training |

### Switching profiles

Edit `active_profile` in `configs/data_volumes.yaml`:
```yaml
active_profile: staging  # dev | staging | prod
```

Or override programmatically before calling `pipeline.run()`:
```python
pipeline.config["volumes"]["active_profile"] = "staging"
pipeline.row_counts = _get_row_counts(pipeline.config)
```

### Adding a new dimension

1. Add the table definition to `configs/schema.yaml`
2. Add a row count entry to `configs/data_volumes.yaml` under each profile
3. Add FK strategies to `configs/relationships.yaml`
4. Add a generator class to `src/generators/dim_generators.py`
5. Register it in `src/pipeline.py → GENERATOR_REGISTRY`
6. Add DDL to `sql/ddl/01_dim_tables.sql`

---

## CPG Domain Reference Data

The generator uses realistic CPG reference data modelled on Kimberly-Clark's portfolio:

**Brands:** Huggies, Pull-Ups, GoodNites, Kleenex, Cottonelle, Scott, Viva, Depend, Poise, U by Kotex, WypAll, Scott Pro, Kleenex Pro

**Product Categories:**
- Baby & Child Care (Diapers, Training Pants, Baby Wipes)
- Personal Care (Feminine Care, Adult Incontinence)
- Family Care (Facial Tissue, Toilet Paper, Paper Towels)
- Professional (Industrial Wipes, Facility Tissue)
- Health & Hygiene (Disinfecting Wipes)

**Vendor Types:** Raw Material, Packaging, Chemical Supplier, Contract Manufacturer, 3PL

**Carrier Types:** Road (FedEx, UPS, J.B. Hunt), Ocean (Maersk, MSC, CMA CGM), Air (DHL, FedEx Express), Rail (DB Schenker)

---

## SQL DDL (Databricks)

The `sql/ddl/` directory contains production-ready Databricks Delta Lake DDL:

```sql
-- Run in order:
-- 1. Create schema and all dimension tables
%run sql/ddl/01_dim_tables.sql

-- 2. Create all fact tables
%run sql/ddl/02_fact_tables.sql

-- 3. Create semantic views and run optimizations
%run sql/ddl/03_views_and_semantic_layer.sql
```

### Semantic Views Available

| View | Description |
|---|---|
| `v_procurement_enriched` | Procurement + vendor + product + warehouse |
| `v_manufacturing_enriched` | Production + plant + product + shift + OEE metrics |
| `v_inventory_health` | Inventory + warehouse + product with health classification |
| `v_shipment_performance` | Shipments + carrier + OTIF flag + cost per unit |
| `v_sales_demand_enriched` | Demand + customer + product + fulfillment band |
| `v_monthly_sc_scorecard` | Cross-domain monthly KPI summary for executive reporting |

---

## Validation

The pipeline runs three validation tiers after generation:

1. **Schema validation** – null checks, type checks, range checks, uniqueness
2. **Business rule validation** – domain logic (e.g. total_cost = qty × unit_cost, flags are mutually exclusive)
3. **Referential integrity** – every FK in every fact table resolves to a valid dimension PK

---

## Knowledge Graph (Neo4j)

The `readme/` directory contains a three-step guide for converting the
generated star-schema data into a CPG supply chain knowledge graph in Neo4j.

| Step | Guide | What it covers |
|---|---|---|
| 1 | [`step1_ontology_neo4j_guide.md`](readme/step1_ontology_neo4j_guide.md) | Define constraints, indexes, and ontology schema in Neo4j Desktop |
| 2 | [`step2_databricks_to_neo4j.md`](readme/step2_databricks_to_neo4j.md) | ETL pipeline: load Delta tables as nodes and aggregated relationships |
| 3 | [`step3_graph_enrichment.md`](readme/step3_graph_enrichment.md) | Compute risk flags, composite scores, and centrality signals in Cypher |
| 4 | [`step4_ai_agent_integration.md`](readme/step4_ai_agent_integration.md) | LangChain + Neo4j chatbox — natural language to Cypher |
| 5 | [`step5_graphrag_knowledge_base.md`](readme/step5_graphrag_knowledge_base.md) | GraphRAG: hybrid agent combining graph traversal + vector document search |
| 6A | [`step6a_anomaly_detection_agent.md`](readme/step6a_anomaly_detection_agent.md) | Anomaly Detection Agent — deterministic threshold-based Cypher detection |
| 6B–D | [`step6_agents.md`](readme/step6_agents.md) | Root Cause, Impact Analysis & Recommendation Agents |
| 9 | [`step9_neo4j_bloom_visualization.md`](readme/step9_neo4j_bloom_visualization.md) | Neo4j Bloom visual perspectives for graph exploration |

See [`readme/README.md`](readme/README.md) for the full implementation path with prerequisites.

---

## Design Principles

| Principle | Implementation |
|---|---|
| **Config-driven** | All volumes, distributions, and FK strategies in YAML |
| **Reproducible** | Seeded `numpy.random.default_rng` passed through entire pipeline |
| **Dependency-aware** | Generation order enforced; facts cannot precede their dimensions |
| **Domain-accurate** | CPG-specific distributions (pareto SKU concentration, seasonal demand, lead time variance) |
| **Scalable** | Profiles scale from ~4K rows (dev) to ~1.4M rows (prod) without code changes |
| **Extensible** | Add new tables by implementing `BaseGenerator` and registering in pipeline |
