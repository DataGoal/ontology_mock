# Step 4: AI Agent Integration
## CPG Supply Chain Knowledge Graph — LangChain + Neo4j + Chatbox

> **What this step builds:** A working chatbox where end users type natural
> language questions and receive grounded answers from your enriched Neo4j
> graph. We wire together: LangChain → Neo4j Aura → Cypher generation →
> structured answers. Everything runs as a Python FastAPI service.
> No Databricks needed in this step.

---

## Architecture of What You Are Building

```
User types question
        │
        ▼
  [ FastAPI /ask endpoint ]
        │
        ▼
  [ LangChain Agent ]
     │         │
     ▼         ▼
 Schema     Question
 Context    + History
     │         │
     └────┬────┘
          ▼
  [ LLM — Claude / GPT ]
  Generates Cypher query
          │
          ▼
  [ Neo4j Aura — your graph ]
  Executes Cypher, returns rows
          │
          ▼
  [ LLM — second pass ]
  Converts rows → natural language answer
          │
          ▼
  JSON response → Chatbox UI
```

---

## Before You Start — Checklist

```
✅ Step 3 complete — graph is enriched with risk flags and scores
✅ Neo4j Aura Free Tier instance is running
✅ You have your Aura connection URI, username, password
✅ Python 3.9+ installed on your local machine
✅ You have an OpenAI API key OR Anthropic API key
```

### Get your Neo4j Aura connection details

In **Neo4j Aura console** (console.neo4j.io):
1. Click your instance
2. Copy the **Connection URI** — looks like:
   `neo4j+s://xxxxxxxx.databases.neo4j.io`
3. Username: `neo4j`
4. Password: the one you saved when the instance was created

> **Important:** Aura uses `neo4j+s://` (encrypted), NOT `bolt://`.
> This is different from what we used in Step 2 for local Desktop.

---

## Section 1 — Project Setup

### 1.1 — Create project folder and virtual environment

```bash
# Run these in your terminal

mkdir cpg_supply_agent
cd cpg_supply_agent

# Create virtual environment
python -m venv venv

# Activate it
# On Mac/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 1.2 — Install all dependencies

```bash
pip install langchain
pip install langchain-community
pip install langchain-openai          # if using OpenAI
pip install langchain-anthropic       # if using Anthropic/Claude
pip install neo4j
pip install fastapi
pip install uvicorn
pip install python-dotenv
pip install pydantic
```

### 1.3 — Create your `.env` file

Create a file called `.env` in your project root. **Never commit this file.**

```bash
# .env

# Neo4j Aura
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_aura_password_here

# Choose ONE of the following LLM providers:

# Option A — OpenAI (recommended for beginners, easiest setup)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Option B — Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx

# App config
APP_PORT=8000
```

### 1.4 — Create project file structure

```
cpg_supply_agent/
├── .env
├── main.py              ← FastAPI app entry point
├── agent/
│   ├── __init__.py
│   ├── graph_chain.py   ← LangChain + Neo4j wiring
│   ├── schema_context.py ← Your ontology as LLM context
│   └── prompts.py       ← System prompts
├── api/
│   ├── __init__.py
│   └── routes.py        ← API endpoints
└── requirements.txt
```

Create the folders:
```bash
mkdir agent api
touch agent/__init__.py api/__init__.py
touch main.py agent/graph_chain.py agent/schema_context.py agent/prompts.py api/routes.py
```

---

## Section 2 — The Ontology Schema Context

This is the most important input to the LLM. Without knowing your graph
schema, the LLM will hallucinate Cypher with wrong node labels and property
names. This file is your ontology fed as system context.

### `agent/schema_context.py`

```python
# agent/schema_context.py
# This is your ontology translated into LLM-readable context.
# The LLM reads this BEFORE generating any Cypher query.
# Keep property names 100% consistent with what Step 1-3 created.

GRAPH_SCHEMA_CONTEXT = """
You are an expert Neo4j Cypher query generator for a CPG (Consumer Packaged Goods)
supply chain knowledge graph. The graph is hosted on Neo4j Aura.

## NODE LABELS AND THEIR KEY PROPERTIES

**Vendor** — Raw material suppliers, co-packers, 3PL vendors
  - vendor_id (string, unique)
  - vendor_name (string)
  - vendor_type (string): 'Raw Material', 'Contract Manufacturer', '3PL'
  - country (string)
  - region (string): 'North America', 'EMEA', 'APAC'
  - tier (string): 'Tier 1', 'Tier 2', 'Tier 3'
  - reliability_score (float, 0.0-1.0)
  - avg_lead_time_days (float)
  - active (boolean)
  [ENRICHED PROPERTIES — computed in Step 3]
  - reliability_tier (string): 'EXCELLENT', 'GOOD', 'AT_RISK', 'CRITICAL'
  - risk_flag (boolean): true if vendor has any risk signal
  - risk_score (integer, 0-100): composite risk score, higher = more risky
  - risk_reasons (list of strings): e.g. ['low_reliability','chronic_under_delivery']
  - supply_centrality (string): 'HIGH_IMPACT', 'MEDIUM_IMPACT', 'LOW_IMPACT'
  - single_source_product_count (integer): products only this vendor supplies
  - under_delivery_flag (boolean)
  - stockout_escalation_flag (boolean)
  - lifetime_spend (float)

**Product** — CPG SKUs across all categories
  - product_id (string, unique)
  - sku (string, unique)
  - product_name (string)
  - category (string): e.g. 'Family Care', 'Baby & Child Care', 'Personal Care'
  - sub_category (string)
  - brand (string)
  - unit_weight_kg (float)
  - packaging_type (string)
  - active (boolean)
  [ENRICHED PROPERTIES]
  - single_source_risk (boolean): only one vendor supplies this product
  - supply_diversity (string): 'SINGLE_SOURCE', 'LOW_DIVERSITY', 'WELL_DIVERSIFIED'
  - vendor_count (integer): number of vendors supplying this product
  - has_any_stockout (boolean): any warehouse stocking this is in stockout
  - has_any_overstock (boolean)
  - demand_pressure_flag (boolean): fulfillment rate below 85%
  - vulnerability_score (integer, 0-100)
  - vulnerability_reasons (list of strings)
  - compounded_risk_flag (boolean): single-source AND vendor is also high risk
  - network_criticality (string): 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
  - total_revenue (float)
  - avg_fulfillment_rate (float)

**Plant** — Manufacturing and conversion facilities
  - plant_id (string, unique)
  - plant_name (string)
  - plant_code (string, unique)
  - country (string)
  - region (string)
  - capacity_units_per_day (float)
  - plant_type (string): 'Assembly', 'Fabrication', 'Packaging', 'Distribution'
  - active (boolean)
  [ENRICHED PROPERTIES]
  - utilization_status (string): 'OVER_CAPACITY', 'OPTIMAL', 'UNDERUTILIZED', 'CRITICALLY_UNDERUTILIZED'
  - performance_flag (boolean)
  - performance_score (integer, 0-100)
  - performance_issues (list of strings): e.g. ['high_defect_rate','excessive_downtime']
  - avg_machine_utilization_pct (float)
  - avg_defect_rate_pct (float)
  - avg_downtime_hours (float)
  - avg_production_attainment (float)

**Warehouse** — Distribution centers, raw material stores, cross-dock
  - warehouse_id (string, unique)
  - warehouse_name (string)
  - warehouse_code (string, unique)
  - type (string): 'Finished Goods', 'Raw Materials', 'Cold Storage', 'Cross-Dock'
  - country (string)
  - region (string)
  - storage_capacity_units (float)
  - active (boolean)
  [ENRICHED PROPERTIES]
  - capacity_status (string): 'OVER_CAPACITY', 'HIGH_UTILIZATION', 'NORMAL', 'LOW_UTILIZATION', 'NEAR_EMPTY'
  - utilization_pct (float)
  - health_flag (boolean)
  - stockout_sku_count (integer)
  - overstock_sku_count (integer)
  - below_reorder_sku_count (integer)
  - is_bottleneck_warehouse (boolean)
  - hub_tier (string): 'MAJOR_HUB', 'REGIONAL_HUB', 'LOCAL_WAREHOUSE'

**Customer** — Retail and B2B customers
  - customer_id (string, unique)
  - customer_name (string)
  - customer_segment (string): 'Retail', 'Enterprise', 'SMB', 'Wholesale'
  - country (string)
  - region (string)
  - channel (string): 'Direct', 'E-Commerce', 'Distributor'
  - active (boolean)
  [ENRICHED PROPERTIES]
  - fulfillment_tier (string): 'EXCELLENT', 'GOOD', 'AT_RISK', 'CRITICAL'
  - fulfillment_risk_flag (boolean)
  - revenue_tier (string): 'TIER_1_KEY_ACCOUNT', 'TIER_2_GROWTH', 'TIER_3_STANDARD', 'TIER_4_SMALL'
  - is_high_value (boolean)
  - vip_at_risk_flag (boolean): high revenue customer with low fulfillment
  - total_revenue (float)
  - avg_fulfillment_rate (float)

**Carrier** — Logistics providers
  - carrier_id (string, unique)
  - carrier_name (string)
  - carrier_type (string): 'Road', 'Air', 'Ocean', 'Rail', 'Courier'
  - country (string)
  - avg_transit_days (float)
  - on_time_delivery_pct (float)
  - active (boolean)
  [ENRICHED PROPERTIES]
  - performance_tier (string): 'PREMIUM', 'STANDARD', 'AT_RISK', 'UNDERPERFORMING'
  - carrier_risk_flag (boolean)
  - coverage_tier (string): 'STRATEGIC_CARRIER', 'REGIONAL_CARRIER', 'LOCAL_CARRIER'
  - network_on_time_pct (float)

**Destination** — Delivery endpoints: retail stores, customer DCs, 3PLs
  - destination_id (string, unique)
  - destination_name (string)
  - destination_type (string): 'Retail Store', 'Customer DC', '3PL Facility', 'End Customer'
  - country (string)
  - region (string)
  - lat (float), lon (float)

## RELATIONSHIP TYPES AND THEIR PROPERTIES

**(Vendor)-[:SUPPLIES]->(Product)**
  - avg_unit_cost (float)
  - avg_lead_time_days (float)
  - avg_delivery_variance_pct (float): negative = under-delivered
  - total_orders (integer)
  - total_spend (float)
  - under_delivery_flag (boolean)

**(Plant)-[:PRODUCES]->(Product)**
  - avg_units_planned (float)
  - avg_units_produced (float)
  - avg_defect_rate_pct (float)
  - avg_throughput_rate (float)
  - avg_machine_utilization_pct (float)
  - avg_downtime_hours (float)
  - avg_attainment_pct (float)
  - total_production_runs (integer)

**(Warehouse)-[:STOCKS]->(Product)**
  - stock_on_hand (float)
  - reorder_point (float)
  - safety_stock (float)
  - stockout_flag (float): 1.0 = stockout, 0.0 = ok
  - overstock_flag (float): 1.0 = overstock, 0.0 = ok

**(Warehouse)-[:SHIPS_TO]->(Destination)**
  - avg_freight_cost (float)
  - avg_transit_days_actual (float)
  - avg_delivery_variance_days (float)
  - on_time_pct (float)
  - total_shipments (integer)
  - route_risk_level (string): 'HIGH_RISK', 'MEDIUM_RISK', 'LOW_RISK', 'ON_TIME'

**(Carrier)-[:HANDLES_ROUTE]->(Destination)**
  - avg_transit_days (float)
  - on_time_pct (float)
  - avg_freight_cost (float)
  - total_shipments (integer)

**(Customer)-[:DEMANDS]->(Product)**
  - total_units_demanded (float)
  - total_units_fulfilled (float)
  - avg_fulfillment_rate_pct (float)
  - total_revenue (float)
  - total_orders (integer)

**(Customer)-[:ORDERS_TO]->(Destination)**
  - total_orders (integer)
  - total_revenue (float)

**(Vendor)-[:ALTERNATIVE_FOR]->(Vendor)**
  - shared_product_count (integer)
  - cost_delta (float): negative = alternative is cheaper
  - lead_time_delta_days (float)
  - substitution_confidence (string): 'High', 'Medium', 'Low'
  - is_actionable_alternative (boolean)
  - recommendation_priority (string): 'HIGH', 'MEDIUM', 'LOW'

## CYPHER RULES — FOLLOW STRICTLY

1. Always use exact node labels: Vendor, Product, Plant, Warehouse,
   Customer, Carrier, Destination (capitalised exactly as shown)
2. Always use exact relationship types in UPPERCASE:
   SUPPLIES, PRODUCES, STOCKS, SHIPS_TO, HANDLES_ROUTE,
   DEMANDS, ORDERS_TO, ALTERNATIVE_FOR
3. Always use LIMIT to prevent large result sets — default LIMIT 25
4. Use OPTIONAL MATCH when a relationship might not exist
5. For risk questions, filter on enriched boolean flags first:
   risk_flag, vulnerability_flag, health_flag, carrier_risk_flag
6. Return human-readable columns, not raw IDs
7. Never use CREATE, MERGE, SET, DELETE — READ ONLY queries only
8. When asked about "worst" or "best", use ORDER BY with LIMIT
9. For path questions, use variable-length relationships: -[:SUPPLIES*1..3]->
10. Always include the node name property in RETURN:
    vendor_name, product_name, plant_name, warehouse_name,
    customer_name, carrier_name, destination_name
"""
```

---

## Section 3 — System Prompts

```python
# agent/prompts.py

CYPHER_GENERATION_PROMPT = """
You are a Neo4j Cypher expert for a CPG supply chain knowledge graph.

{schema}

## YOUR JOB
Given the user question below, generate a single valid READ-ONLY Cypher query
that answers it precisely using the schema above.

## OUTPUT FORMAT
Return ONLY the raw Cypher query.
Do NOT include:
- Markdown code fences (no ```cypher)
- Explanations or comments
- Multiple queries
- Any text before or after the query

## EXAMPLE INPUT → OUTPUT

Question: Which vendors are at high risk?
Cypher:
MATCH (v:Vendor)
WHERE v.risk_flag = true
RETURN v.vendor_name, v.risk_score, v.reliability_tier, v.risk_reasons
ORDER BY v.risk_score DESC
LIMIT 25

Question: What products are single-sourced and in stockout?
Cypher:
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)<-[st:STOCKS]-(w:Warehouse)
WHERE p.single_source_risk = true
  AND st.stockout_flag = 1.0
RETURN p.product_name, p.sku, v.vendor_name, w.warehouse_name,
       st.stock_on_hand, p.vulnerability_score
ORDER BY p.vulnerability_score DESC
LIMIT 25

Question: {question}
Cypher:
"""


ANSWER_GENERATION_PROMPT = """
You are a CPG supply chain analyst assistant.

The user asked: {question}

A database query was run and returned these results:
{results}

## YOUR JOB
Write a clear, concise, business-friendly answer to the user's question
based ONLY on the data returned above.

## RULES
- Be specific — use the actual names, numbers, and values from the results
- Do NOT make up information not in the results
- If results are empty, say no matching records were found and suggest
  the user rephrase or check their filters
- For risk questions, explain WHY something is risky using the risk_reasons field
- For recommendation questions, explain the recommendation clearly with numbers
- Keep the answer under 200 words unless the question needs more detail
- Use plain English, no technical jargon like "Cypher" or "node"
- Format lists with bullet points for readability

Answer:
"""


# Fallback prompt when Cypher generation fails or returns empty results
FALLBACK_PROMPT = """
The user asked: {question}

The graph database query returned no results or could not be executed.

Possible reasons:
1. No data matches the filter criteria
2. The question references an entity not in the graph
3. The question is too broad or too specific

Acknowledge this politely and suggest how the user might rephrase their
question. Offer 2-3 example questions they could ask instead that would
work with the supply chain data available.

Keep the response friendly and under 100 words.
"""
```

---

## Section 4 — The LangChain + Neo4j Agent

```python
# agent/graph_chain.py

import os
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from neo4j.exceptions import CypherSyntaxError, ClientError

# Choose your LLM — uncomment ONE block:

# --- Option A: OpenAI ---
from langchain_openai import ChatOpenAI
def get_llm():
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0,              # temperature=0 = deterministic, critical for Cypher
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

# --- Option B: Anthropic Claude ---
# from langchain_anthropic import ChatAnthropic
# def get_llm():
#     return ChatAnthropic(
#         model="claude-opus-4-6",
#         temperature=0,
#         anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
#     )

load_dotenv()

from agent.schema_context import GRAPH_SCHEMA_CONTEXT
from agent.prompts import (
    CYPHER_GENERATION_PROMPT,
    ANSWER_GENERATION_PROMPT,
    FALLBACK_PROMPT
)


# ── Neo4j connection ──────────────────────────────────────────────────────────

def get_neo4j_graph():
    """
    Returns a LangChain Neo4jGraph connection to your Aura instance.
    Neo4jGraph is a thin wrapper that handles session management.
    """
    return Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
    )


# ── Cypher generation chain ───────────────────────────────────────────────────

def build_cypher_generation_chain(llm):
    """
    Chain 1: Question → Cypher query
    The LLM reads the schema context and generates a Cypher query.
    """
    prompt = PromptTemplate(
        input_variables=["schema", "question"],
        template=CYPHER_GENERATION_PROMPT
    )
    return prompt | llm | StrOutputParser()


# ── Answer generation chain ───────────────────────────────────────────────────

def build_answer_chain(llm):
    """
    Chain 2: Question + DB results → Natural language answer
    The LLM converts raw Cypher results into a readable response.
    """
    prompt = PromptTemplate(
        input_variables=["question", "results"],
        template=ANSWER_GENERATION_PROMPT
    )
    return prompt | llm | StrOutputParser()


def build_fallback_chain(llm):
    """
    Chain 3: Fallback when query fails or returns nothing
    """
    prompt = PromptTemplate(
        input_variables=["question"],
        template=FALLBACK_PROMPT
    )
    return prompt | llm | StrOutputParser()


# ── Main agent function ───────────────────────────────────────────────────────

def run_supply_chain_agent(question: str) -> dict:
    """
    Full pipeline:
      1. Generate Cypher from the question
      2. Execute Cypher against Neo4j Aura
      3. Convert results to natural language answer
      4. Return structured response with all intermediate steps
         (useful for debugging and transparency)
    """
    llm   = get_llm()
    graph = get_neo4j_graph()

    cypher_chain   = build_cypher_generation_chain(llm)
    answer_chain   = build_answer_chain(llm)
    fallback_chain = build_fallback_chain(llm)

    # ── Step 1: Generate Cypher ───────────────────────────────────────────────
    try:
        cypher_query = cypher_chain.invoke({
            "schema":   GRAPH_SCHEMA_CONTEXT,
            "question": question
        })
        # Clean up any accidental markdown fences the LLM might include
        cypher_query = cypher_query.strip()
        cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()

    except Exception as e:
        return {
            "question":     question,
            "cypher_query": None,
            "raw_results":  None,
            "answer":       f"Failed to generate query: {str(e)}",
            "status":       "cypher_generation_failed"
        }

    # ── Step 2: Execute Cypher against Neo4j ─────────────────────────────────
    try:
        raw_results = graph.query(cypher_query)

    except (CypherSyntaxError, ClientError) as e:
        # Cypher was generated but is syntactically invalid
        fallback_answer = fallback_chain.invoke({"question": question})
        return {
            "question":     question,
            "cypher_query": cypher_query,
            "raw_results":  None,
            "answer":       fallback_answer,
            "status":       "cypher_execution_failed",
            "error":        str(e)
        }

    except Exception as e:
        return {
            "question":     question,
            "cypher_query": cypher_query,
            "raw_results":  None,
            "answer":       f"Database error: {str(e)}",
            "status":       "db_error"
        }

    # ── Step 3: Handle empty results ─────────────────────────────────────────
    if not raw_results:
        fallback_answer = fallback_chain.invoke({"question": question})
        return {
            "question":     question,
            "cypher_query": cypher_query,
            "raw_results":  [],
            "answer":       fallback_answer,
            "status":       "no_results"
        }

    # ── Step 4: Generate natural language answer ──────────────────────────────
    # Format raw results cleanly for the LLM
    results_text = "\n".join([str(row) for row in raw_results[:50]])
    # Cap at 50 rows — more than enough context for an answer

    try:
        answer = answer_chain.invoke({
            "question": question,
            "results":  results_text
        })
    except Exception as e:
        # Raw results exist but answer generation failed — still return data
        answer = f"Data retrieved but answer formatting failed: {str(e)}"

    return {
        "question":     question,
        "cypher_query": cypher_query,
        "raw_results":  raw_results,
        "answer":       answer,
        "status":       "success"
    }
```

---

## Section 5 — FastAPI Routes

```python
# api/routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
from agent.graph_chain import run_supply_chain_agent

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class QuestionRequest(BaseModel):
    question: str
    show_cypher: Optional[bool] = False   # set True to see the generated Cypher


class AgentResponse(BaseModel):
    question:     str
    answer:       str
    status:       str
    cypher_query: Optional[str]  = None   # only returned if show_cypher=True
    result_count: Optional[int]  = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AgentResponse)
async def ask_question(request: QuestionRequest):
    """
    Main chatbox endpoint.
    POST { "question": "Which vendors are at high risk?" }
    Returns a natural language answer grounded in the knowledge graph.
    """
    if not request.question or len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="Question is too short.")

    result = run_supply_chain_agent(request.question.strip())

    return AgentResponse(
        question     = result["question"],
        answer       = result["answer"],
        status       = result["status"],
        cypher_query = result["cypher_query"] if request.show_cypher else None,
        result_count = len(result["raw_results"]) if result["raw_results"] else 0
    )


@router.get("/health")
async def health_check():
    """Quick check that the service is running."""
    return {"status": "ok", "service": "CPG Supply Chain AI Agent"}


@router.get("/sample-questions")
async def sample_questions():
    """
    Returns example questions the agent can answer.
    Useful for the chatbox UI to show suggestions.
    """
    return {
        "vendor_risk": [
            "Which vendors are at high risk right now?",
            "Show me all critical vendors with single-source products",
            "Which Tier 1 vendors in APAC have a risk score above 50?",
            "What are the risk reasons for the top 5 most risky vendors?"
        ],
        "inventory": [
            "Which warehouses have stockouts?",
            "Show me products that are in stockout and single-sourced",
            "Which warehouse is operating over capacity?",
            "What products are below their reorder point?"
        ],
        "manufacturing": [
            "Which plants are underperforming?",
            "Show me plants with high defect rates",
            "Which plants are over capacity?",
            "What is the average machine utilization across all plants?"
        ],
        "recommendations": [
            "How can I rebalance vendor supply for at-risk vendors?",
            "Which vendors can replace a high-risk supplier?",
            "Show me actionable vendor alternatives with HIGH priority",
            "Which carrier should I use for North America routes?"
        ],
        "customer_risk": [
            "Which high-value customers have low fulfillment rates?",
            "Show me VIP customers at risk of being under-served",
            "What is the fulfillment rate for Retail segment customers?"
        ]
    }
```

---

## Section 6 — FastAPI Main App

```python
# main.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes import router

load_dotenv()

app = FastAPI(
    title       = "CPG Supply Chain AI Agent",
    description = "Natural language interface to the supply chain knowledge graph",
    version     = "1.0.0"
)

# CORS — allow requests from any frontend during PoC
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "CPG Supply Chain AI Agent is running",
        "docs":    "http://localhost:8000/docs",
        "ask":     "POST http://localhost:8000/api/v1/ask"
    }
```

---

## Section 7 — Run and Test the Agent

### 7.1 — Start the server

```bash
# From your project root, with venv activated:
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### 7.2 — Open the auto-generated API docs

Open your browser: `http://localhost:8000/docs`

This gives you a **built-in Swagger UI** — you can test every endpoint
interactively without writing any frontend code yet.

### 7.3 — Test with curl

```bash
# Basic question
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which vendors are at high risk?"}'
```

```bash
# Show the generated Cypher (useful for debugging)
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which plants are over capacity?", "show_cypher": true}'
```

### 7.4 — Test with Python

```python
# test_agent.py — run this from your terminal: python test_agent.py

import requests

BASE_URL = "http://localhost:8000/api/v1"

test_questions = [
    # Vendor risk
    "Which vendors are at high risk?",
    "Show me vendors with single-source products",
    "Which vendors can replace an at-risk supplier in North America?",

    # Inventory
    "Which warehouses have active stockouts?",
    "Show products that are single-sourced and in stockout",

    # Manufacturing
    "Which plants have the highest defect rates?",
    "Show me plants that are over capacity",

    # Recommendations
    "How can I rebalance vendor supply for critical vendors?",
    "Which actionable vendor alternatives have HIGH priority?",

    # Customer
    "Which VIP customers are at risk of being under-served?",
]

for question in test_questions:
    print(f"\n{'='*60}")
    print(f"Q: {question}")

    response = requests.post(
        f"{BASE_URL}/ask",
        json={"question": question, "show_cypher": True}
    )
    data = response.json()

    print(f"STATUS: {data['status']}")
    if data.get("cypher_query"):
        print(f"CYPHER:\n{data['cypher_query']}")
    print(f"ANSWER:\n{data['answer']}")
    print(f"RESULTS COUNT: {data.get('result_count', 0)}")
```

---

## Section 8 — Simple Chatbox UI (Optional HTML Frontend)

If you want a quick browser chatbox without building a full React app,
create this single HTML file and open it directly in your browser.

```html
<!-- chatbox.html — open in browser, no server needed -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CPG Supply Chain AI Agent</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0f2f5;
      height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .container {
      width: 780px;
      background: white;
      border-radius: 12px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.12);
      display: flex;
      flex-direction: column;
      height: 85vh;
    }
    .header {
      padding: 18px 24px;
      border-bottom: 1px solid #e5e7eb;
      background: #1a1a2e;
      border-radius: 12px 12px 0 0;
      color: white;
    }
    .header h2 { font-size: 16px; font-weight: 600; }
    .header p  { font-size: 12px; opacity: 0.7; margin-top: 2px; }
    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .message { max-width: 85%; }
    .message.user   { align-self: flex-end; }
    .message.agent  { align-self: flex-start; }
    .bubble {
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .user  .bubble { background: #2563eb; color: white; border-radius: 12px 12px 2px 12px; }
    .agent .bubble { background: #f3f4f6; color: #111; border-radius: 12px 12px 12px 2px; }
    .meta { font-size: 11px; color: #9ca3af; margin-top: 4px; }
    .cypher-toggle {
      font-size: 11px;
      color: #6366f1;
      cursor: pointer;
      margin-top: 4px;
      text-decoration: underline;
    }
    .cypher-block {
      display: none;
      margin-top: 8px;
      background: #1e1e2e;
      color: #a6e3a1;
      font-family: monospace;
      font-size: 12px;
      padding: 10px;
      border-radius: 6px;
      white-space: pre-wrap;
    }
    .input-area {
      padding: 16px;
      border-top: 1px solid #e5e7eb;
      display: flex;
      gap: 10px;
    }
    .suggestions {
      padding: 0 16px 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      background: #eff6ff;
      color: #2563eb;
      border: 1px solid #bfdbfe;
      border-radius: 20px;
      padding: 4px 12px;
      font-size: 12px;
      cursor: pointer;
    }
    .chip:hover { background: #dbeafe; }
    input {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
    }
    input:focus { border-color: #2563eb; }
    button {
      padding: 10px 20px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
    }
    button:disabled { background: #93c5fd; cursor: not-allowed; }
    .loading .bubble { color: #9ca3af; }
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>🏭 CPG Supply Chain AI Agent</h2>
    <p>Ask questions about vendors, inventory, manufacturing, shipments, and customers</p>
  </div>

  <div class="suggestions" id="suggestions">
    <span class="chip" onclick="ask(this.innerText)">Which vendors are at high risk?</span>
    <span class="chip" onclick="ask(this.innerText)">Which warehouses have stockouts?</span>
    <span class="chip" onclick="ask(this.innerText)">Which plants are over capacity?</span>
    <span class="chip" onclick="ask(this.innerText)">Show me actionable vendor alternatives</span>
    <span class="chip" onclick="ask(this.innerText)">Which VIP customers are at risk?</span>
  </div>

  <div class="messages" id="messages"></div>

  <div class="input-area">
    <input id="input" type="text" placeholder="Ask about your supply chain..." 
           onkeydown="if(event.key==='Enter') sendQuestion()" />
    <button id="btn" onclick="sendQuestion()">Ask</button>
  </div>
</div>

<script>
  const API = "http://localhost:8000/api/v1/ask";
  let msgId = 0;

  function ask(text) {
    document.getElementById("input").value = text;
    sendQuestion();
  }

  async function sendQuestion() {
    const input = document.getElementById("input");
    const btn   = document.getElementById("btn");
    const question = input.value.trim();
    if (!question) return;

    input.value = "";
    btn.disabled = true;
    addMessage("user", question);
    const loadingId = addMessage("agent", "Thinking...", true);

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, show_cypher: true })
      });
      const data = await res.json();
      updateMessage(loadingId, data.answer, data.cypher_query, data.result_count);
    } catch (e) {
      updateMessage(loadingId, "Error connecting to the agent. Is the server running?");
    }

    btn.disabled = false;
  }

  function addMessage(role, text, loading=false) {
    const id = `msg-${msgId++}`;
    const msgs = document.getElementById("messages");
    msgs.innerHTML += `
      <div class="message ${role} ${loading ? 'loading' : ''}" id="${id}">
        <div class="bubble">${text}</div>
      </div>`;
    msgs.scrollTop = msgs.scrollHeight;
    return id;
  }

  function updateMessage(id, text, cypher=null, count=null) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove("loading");
    let html = `<div class="bubble">${text}</div>`;
    if (count !== null) {
      html += `<div class="meta">${count} record(s) found</div>`;
    }
    if (cypher) {
      const cid = `cypher-${id}`;
      html += `<div class="cypher-toggle" onclick="toggleCypher('${cid}')">
                 Show generated Cypher ↓</div>
               <div class="cypher-block" id="${cid}">${cypher}</div>`;
    }
    el.innerHTML = html;
    document.getElementById("messages").scrollTop = 99999;
  }

  function toggleCypher(id) {
    const el = document.getElementById(id);
    el.style.display = el.style.display === "block" ? "none" : "block";
  }
</script>
</body>
</html>
```

Open `chatbox.html` directly in your browser. Make sure the FastAPI
server is running on port 8000 first.

---

## Section 9 — Troubleshooting Common Issues

| Issue | Cause | Fix |
|---|---|---|
| `AuthError: Neo4j credentials` | Wrong URI or password in `.env` | Double-check `NEO4J_URI` uses `neo4j+s://` not `bolt://` |
| `LLM generates wrong node label` | Schema context not loading | Print `GRAPH_SCHEMA_CONTEXT` in `graph_chain.py` to confirm it loads |
| `Cypher returns 0 results` | LLM used wrong property name | Set `show_cypher: true` and manually run the query in Aura console |
| `openai.AuthenticationError` | Bad API key | Check `.env` has no spaces around the `=` sign |
| `CORS error in browser` | Frontend blocked by CORS | Already handled — `allow_origins=["*"]` in `main.py` |
| `Answer is too generic` | LLM ignoring results | Check `results_text` is not empty before answer chain |
| `ModuleNotFoundError: langchain` | venv not activated | Run `source venv/bin/activate` before `uvicorn` |
| LLM adds backticks to Cypher | Model ignoring format rules | The `.replace("```cypher"...)` strip in `graph_chain.py` handles this |

---

## Section 10 — Verify the Full Pipeline End to End

Run the full pipeline test in order:

```bash
# Terminal 1 — start the server
uvicorn main:app --reload --port 8000

# Terminal 2 — run the test suite
python test_agent.py
```

**Green light checklist:**

```
✅ /health returns {"status": "ok"}
✅ /ask returns status: "success" for at least 7/10 test questions
✅ show_cypher: true returns valid-looking Cypher
✅ Answers reference actual vendor/product/warehouse names from your data
✅ chatbox.html loads and returns answers in the browser
✅ "Show generated Cypher" toggle works in the chatbox
```

---

## Summary: What You Have After Step 4

```
RUNNING SERVICE:
  FastAPI app on localhost:8000
  POST /api/v1/ask       ← main chatbox endpoint
  GET  /api/v1/health    ← health check
  GET  /api/v1/sample-questions ← suggested questions for UI

AGENT PIPELINE:
  User Question
      → LLM reads your full ontology schema as context
      → LLM generates a READ-ONLY Cypher query
      → Cypher executes against Neo4j Aura
      → LLM converts rows into a natural language answer
      → JSON response returned to caller

CHATBOX UI:
  chatbox.html — works in any browser
  Shows suggested question chips
  Displays answers with result count
  "Show generated Cypher" toggle for transparency/debugging

FULL STACK:
  Neo4j Aura        ← enriched knowledge graph (Steps 1-3)
  LangChain         ← agent orchestration
  OpenAI / Claude   ← Cypher generation + answer generation
  FastAPI           ← REST API
  HTML chatbox      ← end user interface
```

---

## Next Step Preview — Step 5: Knowledge Base (GraphRAG)

Step 5 will ingest your unstructured documents (PDFs, Word files, SOPs)
into Neo4j Aura as vector-embedded chunks, linked to your existing graph
nodes. This enables the agent to answer questions that combine structured
graph data WITH institutional knowledge from documents — the full GraphRAG pattern.
```
