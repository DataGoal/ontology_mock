# Steps 6B, 6C, 6D: Root Cause, Impact Analysis & Recommendation Agents
## CPG Supply Chain — Completing the Multi-Agent Pipeline

> **What these steps build:** Three agents that run downstream of the
> Anomaly Detection Agent (Step 6A). Each takes an `AnomalySignal` as
> input and adds a specific layer of intelligence:
>
> - **6B Root Cause Agent** → traverses UPSTREAM to find WHY it happened
> - **6C Impact Analysis Agent** → traverses DOWNSTREAM to find WHO is affected
> - **6D Recommendation Agent** → uses graph heuristics to suggest WHAT to do
>
> All three use pure Cypher for data retrieval and reasoning.
> Claude writes the final narrative only after the logic is complete.

---

## How the Three Agents Connect

```
[AnomalySignal from Step 6A]
           │
           ├──────────────────────────────────────────┐
           │                                          │
           ▼                                          ▼
  [6B Root Cause Agent]                   [6C Impact Analysis Agent]
  Traverses UPSTREAM                      Traverses DOWNSTREAM
  Vendor ← Product ← Warehouse            Warehouse → Destination → Customer
  Scores each node by risk weight         Aggregates revenue + volume at risk
  Returns ranked RootCause list           Returns ImpactReport
           │                                          │
           └──────────────┬───────────────────────────┘
                          │ both feed into
                          ▼
              [6D Recommendation Agent]
              Reads root causes + impact
              Queries ALTERNATIVE_FOR graph
              Applies heuristic scoring
              Returns ranked RecommendationSet
                          │
                          ▼
              [Enriched AnomalySignal]
              root_cause + impact_summary
              + recommendation all populated
              Ready for API / alerting / dashboard
```

---

## Before You Start — Checklist

```
✅ Step 6A complete — AnomalySignal model exists in models/anomaly.py
✅ agent/anomaly_agent.py is working and run_anomaly_detection() runs
✅ Neo4j Aura enriched graph from Steps 1-3 is in place
✅ ontology_mock/ venv activated
✅ Anthropic API key in .env
```

---

## Section 1 — Update Project Structure

Add these files to your existing project:

```
ontology_mock/
├── models/
│   ├── __init__.py
│   ├── anomaly.py             ← unchanged from Step 6A
│   ├── root_cause.py          ← NEW
│   ├── impact.py              ← NEW
│   └── recommendation.py      ← NEW
├── agent/
│   ├── anomaly_agent.py       ← unchanged
│   ├── anomaly_queries.py     ← unchanged
│   ├── root_cause_agent.py    ← NEW
│   ├── impact_agent.py        ← NEW
│   ├── recommendation_agent.py ← NEW
│   └── prompts.py             ← add 3 new prompts
├── api/
│   └── routes.py              ← add new endpoints
└── pipeline.py                ← NEW — orchestrates all 4 agents together
```

```bash
touch models/root_cause.py models/impact.py models/recommendation.py
touch agent/root_cause_agent.py agent/impact_agent.py
touch agent/recommendation_agent.py pipeline.py
```

---

## ══════════════════════════════════════════════════════
## STEP 6B — ROOT CAUSE ANALYSIS AGENT
## ══════════════════════════════════════════════════════

> **What it does:** Takes an AnomalySignal, traverses upstream
> through the graph, scores each upstream node by its own risk
> properties, and returns a ranked list of root causes with
> confidence weights. Claude writes the final explanation.
> Per your architecture: *"Does NOT rely purely on LLM"*

---

## 6B — Section 1: Root Cause Data Model

```python
# models/root_cause.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class RootCauseNode(BaseModel):
    """
    A single node identified as a contributing root cause.
    Scored by its own enriched risk properties, not LLM opinion.
    """
    entity_type:    str            # Vendor / Plant / Carrier / Warehouse
    entity_id:      str
    entity_name:    str
    cause_type:     str            # e.g. VENDOR_UNDER_DELIVERY, PLANT_DOWNTIME
    weight:         float          # 0.0-1.0 — confidence this is the cause
    evidence:       List[str]      # specific properties that support this cause
    raw_properties: Dict[str, Any] # full node data for Claude context


class RootCauseReport(BaseModel):
    """
    Full root cause analysis result for one AnomalySignal.
    """
    anomaly_id:         str
    entity_type:        str
    entity_name:        str
    anomaly_type:       str
    primary_cause:      Optional[RootCauseNode] = None   # highest weighted cause
    contributing_causes: List[RootCauseNode]    = []     # all causes ranked
    traversal_depth:    int                              # hops explored upstream
    narrative:          Optional[str]           = None   # Claude explanation
    cypher_path:        Optional[str]           = None   # the path traversed
```

---

## 6B — Section 2: Root Cause Prompts

Add to your existing `agent/prompts.py`:

```python
# agent/prompts.py — ADD this block

ROOT_CAUSE_PROMPT = """
You are a CPG supply chain root cause analyst.

An anomaly was detected:
  Entity     : {entity_name} ({entity_type})
  Anomaly    : {anomaly_type}
  Severity   : {severity}
  Reasons    : {triggered_reasons}

Upstream graph traversal identified these contributing causes,
ranked by confidence weight (1.0 = highest confidence):

{causes_text}

Write a 3-4 sentence root cause explanation that:
1. Names the PRIMARY root cause clearly (highest weight cause)
2. Explains the chain of events leading to the anomaly
3. References specific evidence from the causes list
4. Uses plain business English — no technical graph terminology

Root Cause Analysis:
"""
```

---

## 6B — Section 3: Root Cause Agent

```python
# agent/root_cause_agent.py

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.anomaly import AnomalySignal
from models.root_cause import RootCauseNode, RootCauseReport
from agent.prompts import ROOT_CAUSE_PROMPT

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = "neo4j"


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=400
    )


# ── Upstream traversal queries ────────────────────────────────────────────────
# Each query walks upstream from the anomaly's entity type.
# Returns nodes with their risk properties for scoring.

def get_upstream_vendors(driver, entity_id: str,
                         entity_type: str) -> List[Dict]:
    """
    Finds upstream Vendor nodes from any entity type.
    Path: Warehouse/Product → (STOCKS/SUPPLIES) → Vendor
    """
    if entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})
              -[:STOCKS]->(p:Product)
              <-[:SUPPLIES]-(v:Vendor)
        RETURN v.vendor_id          AS vendor_id,
               v.vendor_name        AS vendor_name,
               v.risk_flag          AS risk_flag,
               v.risk_score         AS risk_score,
               v.reliability_tier   AS reliability_tier,
               v.risk_reasons       AS risk_reasons,
               v.under_delivery_flag AS under_delivery_flag,
               v.overall_delivery_variance_pct AS delivery_variance,
               v.avg_lead_time_days AS avg_lead_time_days,
               v.single_source_product_count AS single_source_count,
               collect(DISTINCT p.product_name) AS products
        """
    elif entity_type == "Product":
        cypher = """
        MATCH (p:Product {product_id: $entity_id})
              <-[:SUPPLIES]-(v:Vendor)
        RETURN v.vendor_id          AS vendor_id,
               v.vendor_name        AS vendor_name,
               v.risk_flag          AS risk_flag,
               v.risk_score         AS risk_score,
               v.reliability_tier   AS reliability_tier,
               v.risk_reasons       AS risk_reasons,
               v.under_delivery_flag AS under_delivery_flag,
               v.overall_delivery_variance_pct AS delivery_variance,
               v.avg_lead_time_days AS avg_lead_time_days,
               v.single_source_product_count AS single_source_count,
               [p.product_name] AS products
        """
    elif entity_type == "Customer":
        cypher = """
        MATCH (c:Customer {customer_id: $entity_id})
              -[:DEMANDS]->(p:Product)
              <-[:SUPPLIES]-(v:Vendor)
        RETURN v.vendor_id          AS vendor_id,
               v.vendor_name        AS vendor_name,
               v.risk_flag          AS risk_flag,
               v.risk_score         AS risk_score,
               v.reliability_tier   AS reliability_tier,
               v.risk_reasons       AS risk_reasons,
               v.under_delivery_flag AS under_delivery_flag,
               v.overall_delivery_variance_pct AS delivery_variance,
               v.avg_lead_time_days AS avg_lead_time_days,
               v.single_source_product_count AS single_source_count,
               collect(DISTINCT p.product_name) AS products
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


def get_upstream_plants(driver, entity_id: str,
                        entity_type: str) -> List[Dict]:
    """
    Finds upstream Plant nodes from any entity type.
    Path: Warehouse/Product → (STOCKS/PRODUCES) → Plant
    """
    if entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})
              -[:STOCKS]->(p:Product)
              <-[:PRODUCES]-(pl:Plant)
        RETURN pl.plant_id                  AS plant_id,
               pl.plant_name               AS plant_name,
               pl.performance_flag         AS performance_flag,
               pl.performance_score        AS performance_score,
               pl.performance_issues       AS performance_issues,
               pl.utilization_status       AS utilization_status,
               pl.avg_machine_utilization_pct AS utilization_pct,
               pl.avg_defect_rate_pct      AS defect_rate_pct,
               pl.avg_downtime_hours       AS downtime_hours,
               pl.avg_production_attainment AS attainment_pct,
               collect(DISTINCT p.product_name) AS products
        """
    elif entity_type == "Product":
        cypher = """
        MATCH (p:Product {product_id: $entity_id})
              <-[:PRODUCES]-(pl:Plant)
        RETURN pl.plant_id                  AS plant_id,
               pl.plant_name               AS plant_name,
               pl.performance_flag         AS performance_flag,
               pl.performance_score        AS performance_score,
               pl.performance_issues       AS performance_issues,
               pl.utilization_status       AS utilization_status,
               pl.avg_machine_utilization_pct AS utilization_pct,
               pl.avg_defect_rate_pct      AS defect_rate_pct,
               pl.avg_downtime_hours       AS downtime_hours,
               pl.avg_production_attainment AS attainment_pct,
               [p.product_name] AS products
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


def get_upstream_carriers(driver, entity_id: str,
                          entity_type: str) -> List[Dict]:
    """
    Finds upstream Carrier nodes contributing to shipment issues.
    Only applies to Warehouse anomalies (outbound shipping context).
    """
    if entity_type != "Warehouse":
        return []

    cypher = """
    MATCH (w:Warehouse {warehouse_id: $entity_id})
          -[:SHIPS_TO]->(d:Destination)
          <-[:HANDLES_ROUTE]-(ca:Carrier)
    WHERE ca.carrier_risk_flag = true
    RETURN ca.carrier_id              AS carrier_id,
           ca.carrier_name            AS carrier_name,
           ca.performance_tier        AS performance_tier,
           ca.carrier_risk_flag       AS carrier_risk_flag,
           ca.network_on_time_pct     AS on_time_pct,
           ca.network_avg_delay_days  AS avg_delay_days,
           ca.coverage_tier           AS coverage_tier,
           collect(DISTINCT d.destination_name) AS destinations
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


# ── Weighted scoring logic ────────────────────────────────────────────────────

def score_vendor_cause(vendor: Dict) -> Optional[RootCauseNode]:
    """
    Scores a Vendor as a root cause candidate.
    Weight is computed from its enriched risk properties.
    """
    if not vendor.get("risk_flag"):
        return None

    weight   = 0.0
    evidence = []

    risk_score = vendor.get("risk_score") or 0
    weight += min(risk_score / 100.0 * 0.5, 0.5)   # up to 0.5 from risk score

    if vendor.get("under_delivery_flag"):
        weight   += 0.25
        variance  = vendor.get("delivery_variance") or 0
        evidence.append(
            f"under-delivery: {round(variance, 1)}% variance"
        )

    reliability = vendor.get("reliability_tier", "")
    if reliability == "CRITICAL":
        weight   += 0.20
        evidence.append("reliability_tier: CRITICAL")
    elif reliability == "AT_RISK":
        weight   += 0.10
        evidence.append("reliability_tier: AT_RISK")

    if (vendor.get("single_source_count") or 0) > 0:
        weight   += 0.10
        evidence.append(
            f"sole supplier for {vendor['single_source_count']} product(s)"
        )

    reasons = vendor.get("risk_reasons") or []
    evidence.extend(reasons[:3])

    return RootCauseNode(
        entity_type    = "Vendor",
        entity_id      = str(vendor.get("vendor_id", "")),
        entity_name    = str(vendor.get("vendor_name", "")),
        cause_type     = "VENDOR_SUPPLY_FAILURE",
        weight         = round(min(weight, 1.0), 3),
        evidence       = evidence,
        raw_properties = vendor
    )


def score_plant_cause(plant: Dict) -> Optional[RootCauseNode]:
    """
    Scores a Plant as a root cause candidate.
    """
    if not plant.get("performance_flag"):
        return None

    weight   = 0.0
    evidence = []

    perf_score = plant.get("performance_score") or 0
    weight += min(perf_score / 100.0 * 0.5, 0.5)

    defect_rate = plant.get("defect_rate_pct") or 0
    if defect_rate > 5.0:
        weight   += 0.20
        evidence.append(f"defect_rate: {round(defect_rate, 2)}%")

    downtime = plant.get("downtime_hours") or 0
    if downtime > 4.0:
        weight   += 0.15
        evidence.append(f"downtime: {round(downtime, 1)} hrs/shift")

    attainment = plant.get("attainment_pct") or 100
    if attainment < 80:
        weight   += 0.15
        evidence.append(f"attainment: {round(attainment, 1)}%")

    utilization = plant.get("utilization_status", "")
    if utilization == "OVER_CAPACITY":
        weight   += 0.10
        evidence.append("utilization_status: OVER_CAPACITY")

    issues = plant.get("performance_issues") or []
    evidence.extend(issues[:3])

    return RootCauseNode(
        entity_type    = "Plant",
        entity_id      = str(plant.get("plant_id", "")),
        entity_name    = str(plant.get("plant_name", "")),
        cause_type     = "PLANT_PRODUCTION_FAILURE",
        weight         = round(min(weight, 1.0), 3),
        evidence       = evidence,
        raw_properties = plant
    )


def score_carrier_cause(carrier: Dict) -> Optional[RootCauseNode]:
    """
    Scores a Carrier as a root cause candidate.
    """
    if not carrier.get("carrier_risk_flag"):
        return None

    weight   = 0.0
    evidence = []

    on_time = carrier.get("on_time_pct") or 100
    weight += max(0, (85 - on_time) / 85 * 0.5)
    evidence.append(f"on_time_pct: {round(on_time, 1)}%")

    delay = carrier.get("avg_delay_days") or 0
    if delay > 3.0:
        weight   += 0.30
        evidence.append(f"avg_delay: {round(delay, 1)} days")

    perf_tier = carrier.get("performance_tier", "")
    if perf_tier == "UNDERPERFORMING":
        weight   += 0.20
        evidence.append("performance_tier: UNDERPERFORMING")

    return RootCauseNode(
        entity_type    = "Carrier",
        entity_id      = str(carrier.get("carrier_id", "")),
        entity_name    = str(carrier.get("carrier_name", "")),
        cause_type     = "CARRIER_TRANSIT_FAILURE",
        weight         = round(min(weight, 1.0), 3),
        evidence       = evidence,
        raw_properties = carrier
    )


# ── Narrative generation ──────────────────────────────────────────────────────

def generate_root_cause_narrative(
    signal: AnomalySignal,
    causes: List[RootCauseNode],
    llm
) -> str:
    if not causes:
        return ("No upstream causes with sufficient risk signals found. "
                "The anomaly may be isolated or caused by external factors "
                "not captured in the current graph.")

    causes_text = "\n".join([
        f"  [{i+1}] {c.entity_type}: {c.entity_name} "
        f"(weight: {c.weight:.2f}) — {', '.join(c.evidence[:3])}"
        for i, c in enumerate(causes[:5])
    ])

    prompt = PromptTemplate(
        input_variables=["entity_name", "entity_type", "anomaly_type",
                         "severity", "triggered_reasons", "causes_text"],
        template=ROOT_CAUSE_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({
            "entity_name":       signal.entity_name,
            "entity_type":       signal.entity_type,
            "anomaly_type":      signal.anomaly_type,
            "severity":          signal.severity,
            "triggered_reasons": ", ".join(signal.triggered_reasons),
            "causes_text":       causes_text
        }).strip()
    except Exception as e:
        return f"Narrative generation failed: {e}"


# ── Main function ─────────────────────────────────────────────────────────────

def run_root_cause_analysis(
    signal: AnomalySignal,
    with_narrative: bool = True
) -> RootCauseReport:
    """
    Runs root cause analysis for one AnomalySignal.
    Traverses upstream, scores causes, optionally adds Claude narrative.
    """
    driver = get_driver()
    causes = []

    try:
        # Collect upstream candidates
        vendors  = get_upstream_vendors(driver, signal.entity_id,
                                        signal.entity_type)
        plants   = get_upstream_plants(driver, signal.entity_id,
                                       signal.entity_type)
        carriers = get_upstream_carriers(driver, signal.entity_id,
                                         signal.entity_type)

        # Score each candidate
        for v in vendors:
            node = score_vendor_cause(v)
            if node:
                causes.append(node)

        for pl in plants:
            node = score_plant_cause(pl)
            if node:
                causes.append(node)

        for ca in carriers:
            node = score_carrier_cause(ca)
            if node:
                causes.append(node)

    finally:
        driver.close()

    # Rank by weight descending
    causes.sort(key=lambda c: c.weight, reverse=True)

    # Generate narrative
    narrative = None
    if with_narrative:
        llm       = get_llm()
        narrative = generate_root_cause_narrative(signal, causes, llm)

    return RootCauseReport(
        anomaly_id          = signal.anomaly_id,
        entity_type         = signal.entity_type,
        entity_name         = signal.entity_name,
        anomaly_type        = signal.anomaly_type,
        primary_cause       = causes[0] if causes else None,
        contributing_causes = causes,
        traversal_depth     = 2,
        narrative           = narrative
    )
```

---

## ══════════════════════════════════════════════════════
## STEP 6C — IMPACT ANALYSIS AGENT
## ══════════════════════════════════════════════════════

> **What it does:** Takes an AnomalySignal, traverses DOWNSTREAM
> through the graph to quantify who is affected and how much
> revenue and volume is at risk. Pure Cypher — no LLM for scoring.

---

## 6C — Section 1: Impact Data Model

```python
# models/impact.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ImpactedCustomer(BaseModel):
    customer_id:        str
    customer_name:      str
    revenue_at_risk:    float
    units_at_risk:      float
    fulfillment_rate:   float
    revenue_tier:       str
    is_vip:             bool
    affected_products:  List[str]


class ImpactedProduct(BaseModel):
    product_id:         str
    product_name:       str
    sku:                str
    total_stock:        float
    stockout_flag:      bool
    network_criticality: str
    affected_warehouses: List[str]


class ImpactReport(BaseModel):
    """
    Full downstream impact assessment for one AnomalySignal.
    """
    anomaly_id:             str
    entity_type:            str
    entity_name:            str
    anomaly_type:           str

    # Aggregated impact metrics
    total_revenue_at_risk:  float
    total_units_at_risk:    float
    customers_affected:     int
    products_affected:      int
    warehouses_affected:    int
    vip_customers_affected: int

    # Detailed breakdowns
    impacted_customers:     List[ImpactedCustomer] = []
    impacted_products:      List[ImpactedProduct]  = []

    # Narrative
    narrative:              Optional[str] = None
```

---

## 6C — Section 2: Impact Prompts

Add to your existing `agent/prompts.py`:

```python
# agent/prompts.py — ADD this block

IMPACT_ANALYSIS_PROMPT = """
You are a CPG supply chain impact analyst.

An anomaly was detected and downstream impact has been quantified:

Anomaly:
  Entity     : {entity_name} ({entity_type})
  Type       : {anomaly_type}
  Severity   : {severity}

Downstream Impact:
  Total Revenue at Risk : ${total_revenue_at_risk:,.0f}
  Total Units at Risk   : {total_units_at_risk:,.0f}
  Customers Affected    : {customers_affected}
  VIP Customers Affected: {vip_customers_affected}
  Products Affected     : {products_affected}
  Warehouses Affected   : {warehouses_affected}

Top Affected Customers:
{customers_text}

Top Affected Products:
{products_text}

Write a 3-4 sentence impact summary that:
1. States the total financial exposure clearly
2. Highlights VIP customer risk if any are affected
3. Names the most critically impacted products
4. Conveys urgency proportional to the revenue at risk

Impact Summary:
"""
```

---

## 6C — Section 3: Impact Analysis Agent

```python
# agent/impact_agent.py

import os
from typing import List, Dict
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.anomaly import AnomalySignal
from models.impact import ImpactReport, ImpactedCustomer, ImpactedProduct
from agent.prompts import IMPACT_ANALYSIS_PROMPT

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = "neo4j"


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=400
    )


# ── Downstream traversal queries ──────────────────────────────────────────────

def get_downstream_customers(driver, entity_id: str,
                              entity_type: str) -> List[Dict]:
    """
    Finds all downstream Customers affected by the anomaly.
    Path depends on entity type — all paths eventually reach Customer.
    """
    if entity_type == "Vendor":
        cypher = """
        MATCH (v:Vendor {vendor_id: $entity_id})
              -[:SUPPLIES]->(p:Product)
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Product":
        cypher = """
        MATCH (p:Product {product_id: $entity_id})
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               [p.product_name]         AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})
              -[:STOCKS]->(p:Product)
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Plant":
        cypher = """
        MATCH (pl:Plant {plant_id: $entity_id})
              -[:PRODUCES]->(p:Product)
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Carrier":
        cypher = """
        MATCH (ca:Carrier {carrier_id: $entity_id})
              -[:HANDLES_ROUTE]->(d_dest:Destination)
              <-[:ORDERS_TO]-(c:Customer)
        OPTIONAL MATCH (c)-[d:DEMANDS]->(p:Product)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


def get_downstream_products(driver, entity_id: str,
                             entity_type: str) -> List[Dict]:
    """
    Finds all downstream Products affected.
    """
    if entity_type == "Vendor":
        cypher = """
        MATCH (v:Vendor {vendor_id: $entity_id})-[:SUPPLIES]->(p:Product)
        OPTIONAL MATCH (w:Warehouse)-[st:STOCKS]->(p)
        RETURN p.product_id              AS product_id,
               p.product_name           AS product_name,
               p.sku                    AS sku,
               p.network_criticality    AS network_criticality,
               p.has_any_stockout       AS stockout_flag,
               sum(coalesce(st.stock_on_hand, 0)) AS total_stock,
               collect(DISTINCT w.warehouse_name) AS affected_warehouses
        """
    elif entity_type == "Plant":
        cypher = """
        MATCH (pl:Plant {plant_id: $entity_id})-[:PRODUCES]->(p:Product)
        OPTIONAL MATCH (w:Warehouse)-[st:STOCKS]->(p)
        RETURN p.product_id              AS product_id,
               p.product_name           AS product_name,
               p.sku                    AS sku,
               p.network_criticality    AS network_criticality,
               p.has_any_stockout       AS stockout_flag,
               sum(coalesce(st.stock_on_hand, 0)) AS total_stock,
               collect(DISTINCT w.warehouse_name) AS affected_warehouses
        """
    elif entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})-[st:STOCKS]->(p:Product)
        WHERE st.stockout_flag = 1.0 OR st.stock_on_hand < st.reorder_point
        RETURN p.product_id              AS product_id,
               p.product_name           AS product_name,
               p.sku                    AS sku,
               p.network_criticality    AS network_criticality,
               (st.stockout_flag = 1.0) AS stockout_flag,
               st.stock_on_hand         AS total_stock,
               [w.warehouse_name]       AS affected_warehouses
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


# ── Build report ──────────────────────────────────────────────────────────────

def build_impact_report(signal: AnomalySignal,
                        customers: List[Dict],
                        products: List[Dict]) -> ImpactReport:
    impacted_customers = [
        ImpactedCustomer(
            customer_id       = str(c.get("customer_id", "")),
            customer_name     = str(c.get("customer_name", "")),
            revenue_at_risk   = float(c.get("revenue_at_risk") or 0),
            units_at_risk     = float(c.get("units_at_risk") or 0),
            fulfillment_rate  = float(c.get("fulfillment_rate") or 0),
            revenue_tier      = str(c.get("revenue_tier") or ""),
            is_vip            = bool(c.get("is_vip") or False),
            affected_products = [p for p in (c.get("affected_products") or [])
                                 if p is not None]
        )
        for c in customers
    ]

    impacted_products = [
        ImpactedProduct(
            product_id          = str(p.get("product_id", "")),
            product_name        = str(p.get("product_name", "")),
            sku                 = str(p.get("sku") or ""),
            total_stock         = float(p.get("total_stock") or 0),
            stockout_flag       = bool(p.get("stockout_flag") or False),
            network_criticality = str(p.get("network_criticality") or ""),
            affected_warehouses = [w for w in
                                   (p.get("affected_warehouses") or [])
                                   if w is not None]
        )
        for p in products
    ]

    return ImpactReport(
        anomaly_id             = signal.anomaly_id,
        entity_type            = signal.entity_type,
        entity_name            = signal.entity_name,
        anomaly_type           = signal.anomaly_type,
        total_revenue_at_risk  = sum(c.revenue_at_risk
                                     for c in impacted_customers),
        total_units_at_risk    = sum(c.units_at_risk
                                     for c in impacted_customers),
        customers_affected     = len(impacted_customers),
        products_affected      = len(impacted_products),
        warehouses_affected    = len({
            w for p in impacted_products
            for w in p.affected_warehouses
        }),
        vip_customers_affected = sum(1 for c in impacted_customers
                                     if c.is_vip),
        impacted_customers     = impacted_customers,
        impacted_products      = impacted_products,
    )


def generate_impact_narrative(report: ImpactReport, llm) -> str:
    customers_text = "\n".join([
        f"  • {c.customer_name} ({c.revenue_tier}): "
        f"${c.revenue_at_risk:,.0f} at risk"
        f"{'  ⚠️ VIP' if c.is_vip else ''}"
        for c in report.impacted_customers[:5]
    ]) or "  No direct customer data found"

    products_text = "\n".join([
        f"  • {p.product_name} [{p.network_criticality}]"
        f"{'  🔴 STOCKOUT' if p.stockout_flag else ''}"
        for p in report.impacted_products[:5]
    ]) or "  No direct product data found"

    prompt = PromptTemplate(
        input_variables=[
            "entity_name", "entity_type", "anomaly_type", "severity",
            "total_revenue_at_risk", "total_units_at_risk",
            "customers_affected", "vip_customers_affected",
            "products_affected", "warehouses_affected",
            "customers_text", "products_text"
        ],
        template=IMPACT_ANALYSIS_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({
            "entity_name":           report.entity_name,
            "entity_type":           report.entity_type,
            "anomaly_type":          report.anomaly_type,
            "severity":              "HIGH",
            "total_revenue_at_risk": report.total_revenue_at_risk,
            "total_units_at_risk":   report.total_units_at_risk,
            "customers_affected":    report.customers_affected,
            "vip_customers_affected": report.vip_customers_affected,
            "products_affected":     report.products_affected,
            "warehouses_affected":   report.warehouses_affected,
            "customers_text":        customers_text,
            "products_text":         products_text,
        }).strip()
    except Exception as e:
        return f"Narrative generation failed: {e}"


# ── Main function ─────────────────────────────────────────────────────────────

def run_impact_analysis(
    signal: AnomalySignal,
    with_narrative: bool = True
) -> ImpactReport:
    """
    Runs downstream impact analysis for one AnomalySignal.
    """
    driver    = get_driver()
    customers = []
    products  = []

    try:
        customers = get_downstream_customers(driver, signal.entity_id,
                                             signal.entity_type)
        products  = get_downstream_products(driver, signal.entity_id,
                                            signal.entity_type)
    finally:
        driver.close()

    report = build_impact_report(signal, customers, products)

    if with_narrative:
        llm              = get_llm()
        report.narrative = generate_impact_narrative(report, llm)

    return report
```

---

## ══════════════════════════════════════════════════════
## STEP 6D — RECOMMENDATION AGENT
## ══════════════════════════════════════════════════════

> **What it does:** Takes an AnomalySignal + its RootCauseReport +
> ImpactReport, queries the ALTERNATIVE_FOR graph, applies heuristic
> scoring, and returns ranked actionable recommendations.
> Uses graph + heuristics per your architecture. Claude writes
> the final recommendation narrative only.

---

## 6D — Section 1: Recommendation Data Model

```python
# models/recommendation.py

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Recommendation(BaseModel):
    """A single actionable recommendation."""
    rec_id:          str
    action_type:     str       # SWITCH_VENDOR / REBALANCE_INVENTORY /
                               # REROUTE_SHIPMENT / REDISTRIBUTE_PRODUCTION /
                               # EXPEDITE_ORDER / ESCALATE
    priority:        str       # HIGH / MEDIUM / LOW
    confidence:      float     # 0.0-1.0
    title:           str       # short action title
    description:     str       # what to do
    target_entity:   str       # who to act on
    expected_benefit: str      # what outcome to expect
    supporting_data: Dict[str, Any]  # raw graph data backing this rec


class RecommendationSet(BaseModel):
    """All recommendations for one AnomalySignal."""
    anomaly_id:       str
    entity_name:      str
    anomaly_type:     str
    total_recs:       int
    high_priority:    int
    recommendations:  List[Recommendation] = []
    narrative:        Optional[str]        = None
```

---

## 6D — Section 2: Recommendation Prompts

Add to your existing `agent/prompts.py`:

```python
# agent/prompts.py — ADD this block

RECOMMENDATION_PROMPT = """
You are a CPG supply chain strategy analyst.

An anomaly requires action:
  Entity     : {entity_name} ({entity_type})
  Anomaly    : {anomaly_type}
  Root Cause : {root_cause_summary}
  Revenue at Risk: ${revenue_at_risk:,.0f}
  VIP Customers Affected: {vip_count}

The following actions have been identified and scored:

{recommendations_text}

Write a 4-5 sentence recommendation brief that:
1. Acknowledges the root cause in one sentence
2. States the PRIMARY recommended action clearly
3. Explains why this action addresses the root cause
4. Mentions any secondary actions if relevant
5. Notes the expected business benefit

Be specific — use the entity names and numbers provided.
Do not hedge with phrases like "you might consider" —
be direct and action-oriented.

Recommendation:
"""
```

---

## 6D — Section 3: Recommendation Agent

```python
# agent/recommendation_agent.py

import os
import uuid
from typing import List, Dict, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.anomaly import AnomalySignal
from models.root_cause import RootCauseReport
from models.impact import ImpactReport
from models.recommendation import Recommendation, RecommendationSet
from agent.prompts import RECOMMENDATION_PROMPT

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = "neo4j"


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=500
    )


def rec_id() -> str:
    return f"REC-{str(uuid.uuid4())[:8].upper()}"


# ── Graph queries for recommendation data ─────────────────────────────────────

def get_vendor_alternatives(driver, entity_id: str,
                            entity_type: str) -> List[Dict]:
    """
    Fetches ALTERNATIVE_FOR candidates for at-risk vendors.
    Used for SWITCH_VENDOR recommendations.
    """
    if entity_type == "Vendor":
        cypher = """
        MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v:Vendor {vendor_id: $entity_id})
        WHERE a.is_actionable_alternative = true
          AND v_alt.active = true
        RETURN v_alt.vendor_id          AS alt_vendor_id,
               v_alt.vendor_name        AS alt_vendor_name,
               v_alt.reliability_score  AS reliability_score,
               v_alt.reliability_tier   AS reliability_tier,
               v_alt.avg_lead_time_days AS lead_time_days,
               v_alt.tier               AS vendor_tier,
               v_alt.region             AS region,
               a.shared_product_count   AS shared_products,
               a.cost_delta             AS cost_delta,
               a.lead_time_delta_days   AS lead_time_delta,
               a.recommendation_priority AS priority,
               a.substitution_confidence AS confidence
        ORDER BY
            CASE a.recommendation_priority
                WHEN 'HIGH'   THEN 1
                WHEN 'MEDIUM' THEN 2
                ELSE 3
            END,
            v_alt.reliability_score DESC
        LIMIT 5
        """
    elif entity_type in ("Warehouse", "Product"):
        # Find vendors supplying the impacted products
        cypher = """
        MATCH (v_at_risk:Vendor)-[:SUPPLIES]->(p:Product)
        WHERE (p.product_id = $entity_id OR
               EXISTS {
                 MATCH (w:Warehouse {warehouse_id: $entity_id})-[:STOCKS]->(p)
               })
          AND v_at_risk.risk_flag = true
        WITH v_at_risk
        MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v_at_risk)
        WHERE a.is_actionable_alternative = true
          AND v_alt.active = true
        RETURN v_alt.vendor_id          AS alt_vendor_id,
               v_alt.vendor_name        AS alt_vendor_name,
               v_alt.reliability_score  AS reliability_score,
               v_alt.reliability_tier   AS reliability_tier,
               v_alt.avg_lead_time_days AS lead_time_days,
               v_alt.tier               AS vendor_tier,
               v_alt.region             AS region,
               a.shared_product_count   AS shared_products,
               a.cost_delta             AS cost_delta,
               a.lead_time_delta_days   AS lead_time_delta,
               a.recommendation_priority AS priority,
               v_at_risk.vendor_name    AS replaces_vendor
        ORDER BY v_alt.reliability_score DESC
        LIMIT 5
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher, {"entity_id": entity_id})]


def get_rebalance_warehouses(driver, entity_id: str,
                             entity_type: str) -> List[Dict]:
    """
    Finds warehouses with overstock of the affected products
    that could transfer stock to address stockout.
    """
    if entity_type in ("Warehouse", "Product"):
        cypher = """
        MATCH (w_over:Warehouse)-[st:STOCKS]->(p:Product)
        WHERE st.overstock_flag = 1.0
          AND (
            p.product_id = $entity_id
            OR EXISTS {
              MATCH (w_out:Warehouse {warehouse_id: $entity_id})
                    -[:STOCKS]->(p)
            }
          )
        RETURN w_over.warehouse_id       AS warehouse_id,
               w_over.warehouse_name    AS warehouse_name,
               w_over.region            AS region,
               w_over.hub_tier          AS hub_tier,
               p.product_name           AS product_name,
               p.product_id             AS product_id,
               st.stock_on_hand         AS available_stock,
               st.safety_stock          AS safety_stock,
               (st.stock_on_hand - st.safety_stock * 1.5)
                                        AS transferable_units
        ORDER BY transferable_units DESC
        LIMIT 5
        """
        with driver.session(database=NEO4J_DATABASE) as session:
            return [dict(r) for r in session.run(cypher,
                                                 {"entity_id": entity_id})]
    return []


def get_alternative_carriers(driver, entity_id: str,
                             entity_type: str) -> List[Dict]:
    """
    Finds better-performing carriers on the same routes.
    Only relevant for Carrier anomalies.
    """
    if entity_type != "Carrier":
        return []

    cypher = """
    MATCH (ca_bad:Carrier {carrier_id: $entity_id})
          -[:HANDLES_ROUTE]->(d:Destination)
          <-[:HANDLES_ROUTE]-(ca_good:Carrier)
    WHERE ca_good.performance_tier IN ['PREMIUM', 'STANDARD']
      AND ca_good.active = true
      AND ca_good.carrier_id <> ca_bad.carrier_id
    RETURN ca_good.carrier_id           AS carrier_id,
           ca_good.carrier_name         AS carrier_name,
           ca_good.performance_tier     AS performance_tier,
           ca_good.network_on_time_pct  AS on_time_pct,
           ca_good.avg_transit_days     AS avg_transit_days,
           ca_good.carrier_type         AS carrier_type,
           collect(DISTINCT d.destination_name) AS shared_routes,
           count(DISTINCT d)            AS shared_route_count
    ORDER BY ca_good.network_on_time_pct DESC
    LIMIT 3
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher, {"entity_id": entity_id})]


# ── Recommendation builders ───────────────────────────────────────────────────

def build_vendor_switch_recommendations(
    alternatives: List[Dict],
    signal: AnomalySignal
) -> List[Recommendation]:
    recs = []
    for alt in alternatives:
        cost_delta = alt.get("cost_delta") or 0
        priority   = alt.get("priority") or "MEDIUM"
        confidence = 0.9 if priority == "HIGH" else \
                     0.7 if priority == "MEDIUM" else 0.5

        benefit = (
            f"Reliability improves to {alt.get('reliability_score', 0):.2f} "
            f"({alt.get('reliability_tier', 'N/A')}). "
            f"Cost {'savings' if cost_delta <= 0 else 'increase'}: "
            f"${abs(cost_delta):.2f}/unit."
        )

        recs.append(Recommendation(
            rec_id          = rec_id(),
            action_type     = "SWITCH_VENDOR",
            priority        = priority,
            confidence      = confidence,
            title           = f"Switch to {alt.get('alt_vendor_name', 'Alternative Vendor')}",
            description     = (
                f"Redirect procurement from {signal.entity_name} to "
                f"{alt.get('alt_vendor_name')}. "
                f"Covers {alt.get('shared_products', 0)} shared product(s). "
                f"Lead time delta: {alt.get('lead_time_delta', 0):+.1f} days."
            ),
            target_entity   = str(alt.get("alt_vendor_name", "")),
            expected_benefit = benefit,
            supporting_data  = alt
        ))
    return recs


def build_inventory_rebalance_recommendations(
    warehouses: List[Dict],
    signal: AnomalySignal
) -> List[Recommendation]:
    recs = []
    for wh in warehouses:
        transferable = wh.get("transferable_units") or 0
        if transferable <= 0:
            continue

        recs.append(Recommendation(
            rec_id          = rec_id(),
            action_type     = "REBALANCE_INVENTORY",
            priority        = "HIGH",
            confidence      = 0.85,
            title           = f"Transfer stock from {wh.get('warehouse_name')}",
            description     = (
                f"Transfer up to {transferable:,.0f} units of "
                f"{wh.get('product_name')} from "
                f"{wh.get('warehouse_name')} ({wh.get('region')}) "
                f"to address stockout at {signal.entity_name}."
            ),
            target_entity   = str(wh.get("warehouse_name", "")),
            expected_benefit = (
                f"Resolves stockout using existing network stock. "
                f"No new procurement needed."
            ),
            supporting_data  = wh
        ))
    return recs


def build_carrier_reroute_recommendations(
    carriers: List[Dict],
    signal: AnomalySignal
) -> List[Recommendation]:
    recs = []
    for ca in carriers:
        recs.append(Recommendation(
            rec_id          = rec_id(),
            action_type     = "REROUTE_SHIPMENT",
            priority        = "HIGH",
            confidence      = 0.80,
            title           = f"Reroute to {ca.get('carrier_name')}",
            description     = (
                f"Replace {signal.entity_name} with "
                f"{ca.get('carrier_name')} "
                f"({ca.get('performance_tier')}) on "
                f"{ca.get('shared_route_count', 0)} shared route(s). "
                f"On-time rate: {ca.get('on_time_pct', 0):.1f}%."
            ),
            target_entity   = str(ca.get("carrier_name", "")),
            expected_benefit = (
                f"On-time delivery improves from current level to "
                f"{ca.get('on_time_pct', 0):.1f}%."
            ),
            supporting_data  = ca
        ))
    return recs


def build_escalation_recommendation(
    signal: AnomalySignal,
    impact: Optional[ImpactReport]
) -> Recommendation:
    """
    Always added when severity=CRITICAL and no better option exists.
    """
    revenue = impact.total_revenue_at_risk if impact else 0
    return Recommendation(
        rec_id          = rec_id(),
        action_type     = "ESCALATE",
        priority        = "HIGH",
        confidence      = 1.0,
        title           = f"Escalate: {signal.entity_name} requires immediate attention",
        description     = (
            f"CRITICAL anomaly detected on {signal.entity_name}. "
            f"Estimated revenue at risk: ${revenue:,.0f}. "
            f"Escalate to supply chain leadership immediately."
        ),
        target_entity   = signal.entity_name,
        expected_benefit = "Ensures leadership visibility and rapid response.",
        supporting_data  = {"anomaly_score": signal.score,
                            "severity": signal.severity}
    )


# ── Narrative generation ──────────────────────────────────────────────────────

def generate_recommendation_narrative(
    signal:  AnomalySignal,
    report:  RecommendationSet,
    root_cause: Optional[RootCauseReport],
    impact:     Optional[ImpactReport],
    llm
) -> str:
    recs_text = "\n".join([
        f"  [{i+1}] [{r.priority}] {r.action_type}: {r.title}\n"
        f"       {r.description}"
        for i, r in enumerate(report.recommendations[:5])
    ])

    root_summary = (root_cause.narrative or "Root cause not yet determined"
                    if root_cause else "Root cause not yet determined")
    revenue      = impact.total_revenue_at_risk if impact else 0
    vip_count    = impact.vip_customers_affected if impact else 0

    prompt = PromptTemplate(
        input_variables=[
            "entity_name", "entity_type", "anomaly_type",
            "root_cause_summary", "revenue_at_risk",
            "vip_count", "recommendations_text"
        ],
        template=RECOMMENDATION_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({
            "entity_name":          signal.entity_name,
            "entity_type":          signal.entity_type,
            "anomaly_type":         signal.anomaly_type,
            "root_cause_summary":   root_summary[:300],
            "revenue_at_risk":      revenue,
            "vip_count":            vip_count,
            "recommendations_text": recs_text
        }).strip()
    except Exception as e:
        return f"Narrative generation failed: {e}"


# ── Main function ─────────────────────────────────────────────────────────────

def run_recommendation_agent(
    signal:         AnomalySignal,
    root_cause:     Optional[RootCauseReport] = None,
    impact:         Optional[ImpactReport]    = None,
    with_narrative: bool                      = True
) -> RecommendationSet:
    """
    Generates ranked recommendations for one AnomalySignal.
    Optionally uses RootCauseReport and ImpactReport for context.
    """
    driver = get_driver()
    all_recs: List[Recommendation] = []

    try:
        # Vendor switch options
        alternatives = get_vendor_alternatives(driver, signal.entity_id,
                                               signal.entity_type)
        all_recs += build_vendor_switch_recommendations(alternatives, signal)

        # Inventory rebalance options
        rebalance_whs = get_rebalance_warehouses(driver, signal.entity_id,
                                                 signal.entity_type)
        all_recs += build_inventory_rebalance_recommendations(rebalance_whs,
                                                              signal)

        # Carrier rerouting options
        alt_carriers = get_alternative_carriers(driver, signal.entity_id,
                                                signal.entity_type)
        all_recs += build_carrier_reroute_recommendations(alt_carriers, signal)

    finally:
        driver.close()

    # Always add escalation for CRITICAL signals
    if signal.severity == "CRITICAL":
        all_recs.append(build_escalation_recommendation(signal, impact))

    # Sort: HIGH priority first, then by confidence descending
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_recs.sort(
        key=lambda r: (priority_order.get(r.priority, 9), -r.confidence)
    )

    rec_set = RecommendationSet(
        anomaly_id    = signal.anomaly_id,
        entity_name   = signal.entity_name,
        anomaly_type  = signal.anomaly_type,
        total_recs    = len(all_recs),
        high_priority = sum(1 for r in all_recs if r.priority == "HIGH"),
        recommendations = all_recs
    )

    if with_narrative and all_recs:
        llm              = get_llm()
        rec_set.narrative = generate_recommendation_narrative(
            signal, rec_set, root_cause, impact, llm
        )

    return rec_set
```

---

## Section 2 — Full Pipeline Orchestrator

This is the key file that chains all four agents together for one signal.

```python
# pipeline.py
# Orchestrates all 4 agents for one AnomalySignal end-to-end.
# Run directly: python pipeline.py
# Or call run_full_pipeline() from the API.

import json
from typing import List, Optional, Dict
from models.anomaly import AnomalySignal
from models.root_cause import RootCauseReport
from models.impact import ImpactReport
from models.recommendation import RecommendationSet
from agent.anomaly_agent import run_anomaly_detection
from agent.root_cause_agent import run_root_cause_analysis
from agent.impact_agent import run_impact_analysis
from agent.recommendation_agent import run_recommendation_agent


def run_full_pipeline(
    severity_filter:    Optional[str]  = "CRITICAL",
    with_narratives:    bool           = True,
    max_signals:        int            = 10
) -> List[Dict]:
    """
    Runs the complete 4-agent pipeline:
    Detect → Root Cause → Impact → Recommend

    Returns a list of fully enriched signal dicts.
    One dict per anomaly with all four agent outputs combined.
    """
    print("\n🚀 Starting Full Multi-Agent Pipeline")
    print(f"   Severity filter: {severity_filter or 'ALL'}")

    # ── Step 1: Anomaly Detection ─────────────────────────────────────────────
    print("\n[1/4] Running Anomaly Detection Agent...")
    detection_result = run_anomaly_detection(
        severity_filter = severity_filter,
        with_narratives = False,      # skip narrative here — done at end
        max_signals     = max_signals
    )

    signals = [
        AnomalySignal(**s)
        for s in detection_result["signals"]
    ]

    if not signals:
        print("   No anomalies detected. Pipeline complete.")
        return []

    print(f"   {len(signals)} anomaly(ies) detected.")

    # ── Steps 2-4: Per signal ─────────────────────────────────────────────────
    enriched_results = []

    for i, signal in enumerate(signals, 1):
        print(f"\n   Processing signal {i}/{len(signals)}: "
              f"[{signal.severity}] {signal.anomaly_type} — "
              f"{signal.entity_name}")

        # Step 2: Root Cause
        print(f"   [2/4] Root Cause Analysis...")
        root_cause = run_root_cause_analysis(
            signal, with_narrative=with_narratives
        )

        # Step 3: Impact Analysis
        print(f"   [3/4] Impact Analysis...")
        impact = run_impact_analysis(
            signal, with_narrative=with_narratives
        )

        # Step 4: Recommendation
        print(f"   [4/4] Recommendation...")
        recommendations = run_recommendation_agent(
            signal,
            root_cause     = root_cause,
            impact         = impact,
            with_narrative = with_narratives
        )

        enriched_results.append({
            "signal":          signal.model_dump(),
            "root_cause":      root_cause.model_dump(),
            "impact":          impact.model_dump(),
            "recommendations": recommendations.model_dump(),
        })

    print(f"\n✅ Pipeline complete. {len(enriched_results)} signal(s) enriched.")
    return enriched_results


if __name__ == "__main__":
    results = run_full_pipeline(
        severity_filter = "CRITICAL",
        with_narratives = True,
        max_signals     = 5
    )

    for r in results:
        sig  = r["signal"]
        rc   = r["root_cause"]
        imp  = r["impact"]
        rec  = r["recommendations"]

        print(f"\n{'='*65}")
        print(f"ANOMALY   : [{sig['severity']}] {sig['anomaly_type']}")
        print(f"ENTITY    : {sig['entity_name']}")
        print(f"SCORE     : {sig['score']}/100")
        print(f"\nROOT CAUSE: {rc.get('narrative', 'N/A')}")
        print(f"\nIMPACT    : Revenue at risk: "
              f"${imp['total_revenue_at_risk']:,.0f} | "
              f"Customers: {imp['customers_affected']} | "
              f"VIPs: {imp['vip_customers_affected']}")
        if imp.get("narrative"):
            print(f"           {imp['narrative']}")
        print(f"\nRECOMMENDATIONS ({rec['high_priority']} HIGH priority):")
        for rx in rec["recommendations"][:3]:
            print(f"  [{rx['priority']}] {rx['title']}")
        if rec.get("narrative"):
            print(f"\n  {rec['narrative']}")
```

---

## Section 3 — Add API Endpoints

Add these to your existing `api/routes.py`:

```python
# api/routes.py — ADD these blocks

from agent.root_cause_agent import run_root_cause_analysis     # add to imports
from agent.impact_agent import run_impact_analysis             # add to imports
from agent.recommendation_agent import run_recommendation_agent # add to imports
from pipeline import run_full_pipeline                         # add to imports
from models.anomaly import AnomalySignal                       # add to imports


# ── Pipeline endpoint — runs all 4 agents for CRITICAL signals ────────────────

@router.post("/pipeline/run")
async def run_pipeline(
    severity_filter: Optional[str] = "CRITICAL",
    max_signals:     int            = 10,
    with_narratives: bool           = True
):
    """
    Runs the complete 4-agent pipeline.
    Detect → Root Cause → Impact → Recommend

    Returns fully enriched signal list sorted by severity + score.
    """
    results = run_full_pipeline(
        severity_filter = severity_filter,
        with_narratives = with_narratives,
        max_signals     = max_signals
    )
    return {
        "total_processed": len(results),
        "severity_filter": severity_filter,
        "results": results
    }


# ── Individual agent endpoints (useful for testing each agent alone) ──────────

@router.post("/anomaly/{anomaly_id}/root-cause")
async def get_root_cause(anomaly_id: str, signal: dict):
    """
    Runs root cause analysis for a provided AnomalySignal dict.
    Pass the signal dict from /anomaly/detect in the request body.
    """
    s      = AnomalySignal(**signal)
    result = run_root_cause_analysis(s, with_narrative=True)
    return result.model_dump()


@router.post("/anomaly/{anomaly_id}/impact")
async def get_impact(anomaly_id: str, signal: dict):
    """Runs impact analysis for a provided AnomalySignal dict."""
    s      = AnomalySignal(**signal)
    result = run_impact_analysis(s, with_narrative=True)
    return result.model_dump()


@router.post("/anomaly/{anomaly_id}/recommend")
async def get_recommendations(anomaly_id: str, signal: dict):
    """Runs recommendation agent for a provided AnomalySignal dict."""
    s      = AnomalySignal(**signal)
    result = run_recommendation_agent(s, with_narrative=True)
    return result.model_dump()
```

---

## Section 4 — Test the Complete Pipeline

```python
# test_pipeline.py

from pipeline import run_full_pipeline

print("── TEST 1: Full CRITICAL pipeline (no narratives — fast) ──")
results = run_full_pipeline(
    severity_filter = "CRITICAL",
    with_narratives = False,
    max_signals     = 5
)
print(f"Signals processed: {len(results)}")
for r in results[:2]:
    sig = r["signal"]
    rc  = r["root_cause"]
    imp = r["impact"]
    rec = r["recommendations"]
    print(f"\n  Signal    : {sig['anomaly_type']} — {sig['entity_name']}")
    print(f"  Root cause: {len(rc['contributing_causes'])} cause(s) found")
    print(f"  Primary   : {rc['primary_cause']['entity_name'] if rc['primary_cause'] else 'None'}")
    print(f"  Impact    : ${imp['total_revenue_at_risk']:,.0f} revenue at risk")
    print(f"  Recs      : {rec['total_recs']} total, {rec['high_priority']} HIGH")

print("\n── TEST 2: Single signal end-to-end with narratives ──")
results = run_full_pipeline(
    severity_filter = "CRITICAL",
    with_narratives = True,
    max_signals     = 1
)
if results:
    r   = results[0]
    rec = r["recommendations"]
    print(f"\n  Recommendation narrative:\n  {rec.get('narrative', 'None')}")
```

---

## Section 5 — Verify the Full Multi-Agent System

```
✅ python pipeline.py runs without errors
✅ Each signal has root_cause, impact, recommendations populated
✅ root_cause.primary_cause is not None for CRITICAL vendor signals
✅ impact.total_revenue_at_risk > 0 for vendor/warehouse signals
✅ recommendations list has at least 1 HIGH priority item for CRITICAL
✅ CRITICAL signals include an ESCALATE recommendation
✅ /api/v1/pipeline/run returns enriched results via API
✅ with_narratives=True produces Claude-written text in all narrative fields
✅ with_narratives=False completes in < 5 seconds (no LLM calls)
```

---

## Summary: What You Have After Steps 6B, 6C, 6D

```
NEW FILES:
  models/root_cause.py          ← RootCauseNode + RootCauseReport models
  models/impact.py              ← ImpactedCustomer + ImpactReport models
  models/recommendation.py      ← Recommendation + RecommendationSet models
  agent/root_cause_agent.py     ← upstream traversal + weighted scoring
  agent/impact_agent.py         ← downstream traversal + revenue aggregation
  agent/recommendation_agent.py ← graph heuristics + ranked action set
  pipeline.py                   ← 4-agent orchestrator

NEW ENDPOINTS:
  POST /api/v1/pipeline/run                ← full 4-agent pipeline
  POST /api/v1/anomaly/{id}/root-cause     ← single signal root cause
  POST /api/v1/anomaly/{id}/impact         ← single signal impact
  POST /api/v1/anomaly/{id}/recommend      ← single signal recommendations

AGENT BEHAVIOURS:
  6B Root Cause   → upstream traversal (Warehouse←Product←Vendor/Plant)
                    weighted scoring per risk property
                    Claude writes explanation narrative
  6C Impact       → downstream traversal (Vendor→Product→Customer)
                    revenue + volume aggregation per customer
                    Claude writes impact brief
  6D Recommendation → ALTERNATIVE_FOR graph queries
                      SWITCH_VENDOR / REBALANCE / REROUTE / ESCALATE
                      priority + confidence scoring
                      Claude writes action brief

COMPLETE PIPELINE FLOW:
  AnomalySignal
    → Root Cause (why did it happen?)
    → Impact     (who is affected + how much revenue?)
    → Recommend  (what should we do?)
    → Enriched result with all four outputs combined

WHAT CLAUDE DOES AND DOESN'T DO:
  ✅ Writes human-readable narratives (explanation, impact brief, action brief)
  ❌ Does NOT detect anomalies — pure Cypher thresholds
  ❌ Does NOT score root causes — pure property-based weights
  ❌ Does NOT rank recommendations — pure graph heuristics
  This makes the system deterministic, auditable, and trustworthy
```
