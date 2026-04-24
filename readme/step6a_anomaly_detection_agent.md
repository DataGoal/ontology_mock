# Step 6A: Anomaly Detection Agent
## CPG Supply Chain — Detecting Anomalies from the Enriched Knowledge Graph

> **What this step builds:** A dedicated Anomaly Detection Agent that
> monitors your enriched Neo4j graph, detects abnormal patterns across
> Vendors, Products, Plants, Warehouses, Carriers and Customers using
> threshold-based Cypher queries, and emits structured anomaly signals.
> Detection is entirely graph-driven — **no LLM involved in detection**.
> Claude is used only for writing the human-readable narrative summary
> of what was found. This keeps detection deterministic and auditable.

---

## How This Agent Fits in Your Architecture

```
Your Architecture Diagram — Multi-Agent Layer:

  ┌─────────────────────────────────────────────────┐
  │         ANOMALY DETECTION AGENT  ← THIS STEP    │
  │  • Monitors graph continuously                   │
  │  • Detects abnormal patterns using               │
  │    thresholds & trends                           │
  └──────────────────┬──────────────────────────────┘
                     │ emits AnomalySignal objects
                     ▼
          Root Cause Agent  (Step 6B)
          Impact Analysis Agent  (Step 6C)
          Recommendation Agent   (Step 6D)

Signal & Feature Engineering Layer feeds INTO this agent:
  • Delivery delays, stockouts
  • High defect rates, vendor unreliability
  (all pre-computed as enriched properties in Step 3)
```

The Anomaly Detection Agent is the **entry point** of your multi-agent
pipeline. Every downstream agent in Steps 6B, 6C, 6D depends on the
structured `AnomalySignal` objects this agent produces.

---

## What an Anomaly Signal Looks Like

Every anomaly detected by this agent becomes a structured Python object:

```python
AnomalySignal(
    anomaly_id        = "ANO-20250423-001",
    entity_type       = "Vendor",
    entity_id         = "v-0042",
    entity_name       = "Pacific Fiber Group",
    anomaly_type      = "VENDOR_CRITICAL_RISK",
    severity          = "CRITICAL",          # CRITICAL / HIGH / MEDIUM
    score             = 85,                  # 0-100, higher = worse
    triggered_reasons = ["low_reliability", "chronic_under_delivery",
                         "single_source_product_count: 3"],
    affected_products = ["Kleenex 48-Roll", "Scott Tissue 24pk"],
    affected_count    = 2,
    detected_at       = "2025-04-23T09:00:00",
    raw_data          = { ...full node properties... }
)
```

This object is serialisable to JSON — every downstream agent receives
it as input and knows exactly what entity triggered and why.

---

## Before You Start — Checklist

```
✅ Steps 1-5 complete
✅ Neo4j Aura instance running with enriched graph from Step 3
✅ cpg_supply_agent/ project with venv activated
✅ Claude (Anthropic) API key in .env
✅ FastAPI server from Step 4 is the base we extend
```

---

## Section 1 — Update Project Structure

Add these new files to your existing project:

```
cpg_supply_agent/
├── .env
├── main.py
├── agent/
│   ├── __init__.py
│   ├── graph_chain.py         ← unchanged
│   ├── schema_context.py      ← unchanged
│   ├── prompts.py             ← add anomaly narrative prompt
│   ├── rag_chain.py           ← unchanged
│   ├── document_loader.py     ← unchanged
│   ├── anomaly_agent.py       ← NEW — detection + signal emission
│   └── anomaly_queries.py     ← NEW — all Cypher detection queries
├── models/
│   ├── __init__.py
│   └── anomaly.py             ← NEW — AnomalySignal data model
├── api/
│   ├── __init__.py
│   └── routes.py              ← add anomaly endpoints
└── ingest.py
```

```bash
# Create new files
mkdir models
touch models/__init__.py
touch models/anomaly.py
touch agent/anomaly_agent.py
touch agent/anomaly_queries.py
```

---

## Section 2 — The AnomalySignal Data Model

```python
# models/anomaly.py
# The canonical data structure for every anomaly this agent detects.
# Every downstream agent (Root Cause, Impact, Recommendation) receives
# one of these as input — so keep it consistent.

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class AnomalySignal(BaseModel):
    """
    A single detected anomaly from the knowledge graph.
    Immutable once created — downstream agents read but never modify it.
    """
    # Identity
    anomaly_id:         str            # e.g. "ANO-20250423-001"
    entity_type:        str            # Vendor / Product / Plant / Warehouse / Carrier / Customer
    entity_id:          str            # the node's primary key UUID
    entity_name:        str            # human-readable name for display

    # Classification
    anomaly_type:       str            # see ANOMALY_TYPE registry below
    severity:           str            # CRITICAL / HIGH / MEDIUM
    score:              int            # 0-100 composite, higher = worse

    # Explanation
    triggered_reasons:  List[str]      # list of human-readable reasons
    affected_products:  List[str]      # product names impacted (if applicable)
    affected_count:     int            # count of affected downstream entities

    # Metadata
    detected_at:        str            # ISO timestamp
    raw_data:           Dict[str, Any] # full node properties for downstream use

    # Optional enrichment added by downstream agents
    root_cause:         Optional[str]  = None
    impact_summary:     Optional[str]  = None
    recommendation:     Optional[str]  = None
    narrative:          Optional[str]  = None   # Claude-written summary


# ── Anomaly type registry ─────────────────────────────────────────────────────
# Every anomaly_type string this agent can emit, with its severity band
# and the entity type it applies to.

ANOMALY_TYPE_REGISTRY = {

    # Vendor anomalies
    "VENDOR_CRITICAL_RISK": {
        "entity_type": "Vendor",
        "severity":    "CRITICAL",
        "description": "Vendor risk_score >= 60 or reliability_tier = CRITICAL"
    },
    "VENDOR_HIGH_RISK": {
        "entity_type": "Vendor",
        "severity":    "HIGH",
        "description": "Vendor risk_score >= 30 or reliability_tier = AT_RISK"
    },
    "VENDOR_UNDER_DELIVERY": {
        "entity_type": "Vendor",
        "severity":    "HIGH",
        "description": "Vendor avg_delivery_variance_pct < -15 across products"
    },
    "VENDOR_SINGLE_SOURCE_CRITICAL": {
        "entity_type": "Vendor",
        "severity":    "CRITICAL",
        "description": "Vendor is sole supplier for 1+ products AND is high risk"
    },

    # Product anomalies
    "PRODUCT_COMPOUNDED_RISK": {
        "entity_type": "Product",
        "severity":    "CRITICAL",
        "description": "Single-source product whose only vendor is also high risk"
    },
    "PRODUCT_ACTIVE_STOCKOUT": {
        "entity_type": "Product",
        "severity":    "CRITICAL",
        "description": "Product has stockout_flag=1 in at least one warehouse"
    },
    "PRODUCT_LOW_FULFILLMENT": {
        "entity_type": "Product",
        "severity":    "HIGH",
        "description": "Product avg_fulfillment_rate < 85% across customers"
    },
    "PRODUCT_NO_VENDOR": {
        "entity_type": "Product",
        "severity":    "CRITICAL",
        "description": "Active product with zero vendor supply relationships"
    },

    # Plant anomalies
    "PLANT_OVER_CAPACITY": {
        "entity_type": "Plant",
        "severity":    "HIGH",
        "description": "Plant machine utilization > 90%"
    },
    "PLANT_HIGH_DEFECT_RATE": {
        "entity_type": "Plant",
        "severity":    "HIGH",
        "description": "Plant avg_defect_rate_pct > 5%"
    },
    "PLANT_EXCESSIVE_DOWNTIME": {
        "entity_type": "Plant",
        "severity":    "MEDIUM",
        "description": "Plant avg_downtime_hours > 4 per shift"
    },
    "PLANT_LOW_ATTAINMENT": {
        "entity_type": "Plant",
        "severity":    "MEDIUM",
        "description": "Plant production attainment < 80% of planned"
    },

    # Warehouse anomalies
    "WAREHOUSE_STOCKOUT": {
        "entity_type": "Warehouse",
        "severity":    "CRITICAL",
        "description": "Warehouse has 1+ SKUs in stockout"
    },
    "WAREHOUSE_OVER_CAPACITY": {
        "entity_type": "Warehouse",
        "severity":    "HIGH",
        "description": "Warehouse utilization > 95%"
    },
    "WAREHOUSE_BOTTLENECK": {
        "entity_type": "Warehouse",
        "severity":    "HIGH",
        "description": "Warehouse is sole stocking point for product(s) in stockout"
    },
    "WAREHOUSE_BELOW_REORDER": {
        "entity_type": "Warehouse",
        "severity":    "MEDIUM",
        "description": "1+ SKUs below reorder point — replenishment needed"
    },

    # Carrier anomalies
    "CARRIER_UNDERPERFORMING": {
        "entity_type": "Carrier",
        "severity":    "HIGH",
        "description": "Carrier on-time delivery < 75% across routes"
    },
    "CARRIER_HIGH_DELAY": {
        "entity_type": "Carrier",
        "severity":    "MEDIUM",
        "description": "Carrier avg_delay_days > 3 days across routes"
    },

    # Customer anomalies
    "CUSTOMER_VIP_AT_RISK": {
        "entity_type": "Customer",
        "severity":    "CRITICAL",
        "description": "High-value customer with fulfillment rate < 85%"
    },
    "CUSTOMER_LOW_FULFILLMENT": {
        "entity_type": "Customer",
        "severity":    "HIGH",
        "description": "Any customer with avg fulfillment rate < 70%"
    },
}
```

---

## Section 3 — Anomaly Detection Cypher Queries

```python
# agent/anomaly_queries.py
# Pure Cypher queries — one per anomaly type.
# Each query returns rows that the anomaly agent converts into AnomalySignal objects.
# NO LLM here — all detection is threshold-based graph traversal.
#
# Query contract:
#   Every query MUST return these columns at minimum:
#     entity_id, entity_name, score, triggered_reasons (list), affected_products (list)
#   Additional columns are passed through to raw_data.

# ═════════════════════════════════════════════════════════════════════════════
# VENDOR QUERIES
# ═════════════════════════════════════════════════════════════════════════════

VENDOR_CRITICAL_RISK = """
MATCH (v:Vendor)
WHERE v.risk_flag = true
  AND v.risk_score >= 60
OPTIONAL MATCH (v)-[:SUPPLIES]->(p:Product)
WITH v, collect(DISTINCT p.product_name) AS affected_products
RETURN v.vendor_id                  AS entity_id,
       v.vendor_name                AS entity_name,
       v.risk_score                 AS score,
       v.risk_reasons               AS triggered_reasons,
       affected_products            AS affected_products,
       size(affected_products)      AS affected_count,
       v.reliability_tier           AS reliability_tier,
       v.tier                       AS vendor_tier,
       v.region                     AS region,
       v.single_source_product_count AS single_source_count,
       v.lifetime_spend             AS lifetime_spend
ORDER BY v.risk_score DESC
"""

VENDOR_HIGH_RISK = """
MATCH (v:Vendor)
WHERE v.risk_flag = true
  AND v.risk_score >= 30
  AND v.risk_score < 60
OPTIONAL MATCH (v)-[:SUPPLIES]->(p:Product)
WITH v, collect(DISTINCT p.product_name) AS affected_products
RETURN v.vendor_id                  AS entity_id,
       v.vendor_name                AS entity_name,
       v.risk_score                 AS score,
       v.risk_reasons               AS triggered_reasons,
       affected_products            AS affected_products,
       size(affected_products)      AS affected_count,
       v.reliability_tier           AS reliability_tier,
       v.tier                       AS vendor_tier,
       v.region                     AS region
ORDER BY v.risk_score DESC
"""

VENDOR_UNDER_DELIVERY = """
MATCH (v:Vendor)
WHERE v.under_delivery_flag = true
  AND v.overall_delivery_variance_pct < -15.0
OPTIONAL MATCH (v)-[s:SUPPLIES]->(p:Product)
WHERE s.under_delivery_flag = true
WITH v,
     collect(DISTINCT p.product_name) AS affected_products,
     avg(s.avg_delivery_variance_pct) AS worst_variance
RETURN v.vendor_id                     AS entity_id,
       v.vendor_name                   AS entity_name,
       abs(toInteger(worst_variance))  AS score,
       ['chronic_under_delivery',
        'avg_variance: ' + toString(round(worst_variance, 1)) + '%']
                                       AS triggered_reasons,
       affected_products               AS affected_products,
       size(affected_products)         AS affected_count,
       round(worst_variance, 2)        AS delivery_variance_pct,
       v.reliability_score             AS reliability_score
ORDER BY worst_variance ASC
"""

VENDOR_SINGLE_SOURCE_CRITICAL = """
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WHERE v.risk_flag = true
  AND p.single_source_risk = true
WITH v, collect(DISTINCT p.product_name) AS critical_products
WHERE size(critical_products) >= 1
RETURN v.vendor_id                AS entity_id,
       v.vendor_name              AS entity_name,
       (v.risk_score + size(critical_products) * 10)
                                  AS score,
       ['sole_vendor_for_' + toString(size(critical_products)) + '_products',
        'vendor_risk_score: ' + toString(v.risk_score)]
                                  AS triggered_reasons,
       critical_products          AS affected_products,
       size(critical_products)    AS affected_count,
       v.risk_score               AS vendor_risk_score,
       v.reliability_tier         AS reliability_tier
ORDER BY score DESC
"""


# ═════════════════════════════════════════════════════════════════════════════
# PRODUCT QUERIES
# ═════════════════════════════════════════════════════════════════════════════

PRODUCT_COMPOUNDED_RISK = """
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WHERE p.compounded_risk_flag = true
  AND v.risk_flag = true
RETURN p.product_id                AS entity_id,
       p.product_name              AS entity_name,
       (p.vulnerability_score + v.risk_score) / 2
                                   AS score,
       p.vulnerability_reasons     AS triggered_reasons,
       [p.product_name]            AS affected_products,
       1                           AS affected_count,
       p.vulnerability_score       AS vulnerability_score,
       v.vendor_name               AS sole_vendor_name,
       v.risk_score                AS sole_vendor_risk_score,
       p.category                  AS category,
       p.network_criticality       AS network_criticality
ORDER BY score DESC
"""

PRODUCT_ACTIVE_STOCKOUT = """
MATCH (p:Product)<-[st:STOCKS]-(w:Warehouse)
WHERE st.stockout_flag = 1.0
WITH p,
     collect(DISTINCT w.warehouse_name) AS stockout_warehouses,
     count(DISTINCT w)                  AS stockout_wh_count,
     sum(st.stock_on_hand)              AS total_stock
RETURN p.product_id                AS entity_id,
       p.product_name              AS entity_name,
       (50 + stockout_wh_count * 10)
                                   AS score,
       ['active_stockout_in_' + toString(stockout_wh_count) + '_warehouse(s)',
        'total_stock_on_hand: ' + toString(round(total_stock, 0))]
                                   AS triggered_reasons,
       [p.product_name]            AS affected_products,
       stockout_wh_count           AS affected_count,
       stockout_warehouses         AS stockout_warehouses,
       p.single_source_risk        AS single_source_risk,
       p.network_criticality       AS network_criticality,
       p.category                  AS category
ORDER BY score DESC
"""

PRODUCT_LOW_FULFILLMENT = """
MATCH (p:Product)
WHERE p.demand_pressure_flag = true
  AND p.avg_fulfillment_rate < 85.0
  AND p.avg_fulfillment_rate IS NOT NULL
RETURN p.product_id                AS entity_id,
       p.product_name              AS entity_name,
       toInteger(100 - p.avg_fulfillment_rate)
                                   AS score,
       ['fulfillment_rate: ' + toString(round(p.avg_fulfillment_rate, 1)) + '%',
        'below_85pct_threshold']   AS triggered_reasons,
       [p.product_name]            AS affected_products,
       p.customer_count            AS affected_count,
       p.avg_fulfillment_rate      AS fulfillment_rate,
       p.total_revenue             AS total_revenue,
       p.network_criticality       AS network_criticality
ORDER BY score DESC
"""

PRODUCT_NO_VENDOR = """
MATCH (p:Product)
WHERE p.active = true
  AND p.vendor_count = 0
RETURN p.product_id                AS entity_id,
       p.product_name              AS entity_name,
       100                         AS score,
       ['no_active_vendor_supply', 'orphaned_product']
                                   AS triggered_reasons,
       [p.product_name]            AS affected_products,
       0                           AS affected_count,
       p.category                  AS category,
       p.network_criticality       AS network_criticality
"""


# ═════════════════════════════════════════════════════════════════════════════
# PLANT QUERIES
# ═════════════════════════════════════════════════════════════════════════════

PLANT_OVER_CAPACITY = """
MATCH (pl:Plant)
WHERE pl.utilization_status = 'OVER_CAPACITY'
  AND pl.avg_machine_utilization_pct > 90.0
OPTIONAL MATCH (pl)-[:PRODUCES]->(p:Product)
WITH pl, collect(DISTINCT p.product_name) AS affected_products
RETURN pl.plant_id                 AS entity_id,
       pl.plant_name               AS entity_name,
       toInteger(pl.avg_machine_utilization_pct)
                                   AS score,
       ['machine_utilization: ' + toString(pl.avg_machine_utilization_pct) + '%',
        'status: OVER_CAPACITY']   AS triggered_reasons,
       affected_products           AS affected_products,
       size(affected_products)     AS affected_count,
       pl.avg_machine_utilization_pct AS utilization_pct,
       pl.capacity_units_per_day   AS capacity_units_per_day,
       pl.region                   AS region
ORDER BY pl.avg_machine_utilization_pct DESC
"""

PLANT_HIGH_DEFECT_RATE = """
MATCH (pl:Plant)
WHERE pl.avg_defect_rate_pct > 5.0
  AND pl.avg_defect_rate_pct IS NOT NULL
OPTIONAL MATCH (pl)-[:PRODUCES]->(p:Product)
WITH pl, collect(DISTINCT p.product_name) AS affected_products
RETURN pl.plant_id                 AS entity_id,
       pl.plant_name               AS entity_name,
       toInteger(pl.avg_defect_rate_pct * 10)
                                   AS score,
       ['defect_rate: ' + toString(round(pl.avg_defect_rate_pct, 2)) + '%',
        'exceeds_5pct_threshold']  AS triggered_reasons,
       affected_products           AS affected_products,
       size(affected_products)     AS affected_count,
       pl.avg_defect_rate_pct      AS defect_rate_pct,
       pl.avg_downtime_hours       AS downtime_hours,
       pl.region                   AS region
ORDER BY pl.avg_defect_rate_pct DESC
"""

PLANT_EXCESSIVE_DOWNTIME = """
MATCH (pl:Plant)
WHERE pl.avg_downtime_hours > 4.0
  AND pl.avg_downtime_hours IS NOT NULL
OPTIONAL MATCH (pl)-[:PRODUCES]->(p:Product)
WITH pl, collect(DISTINCT p.product_name) AS affected_products
RETURN pl.plant_id                 AS entity_id,
       pl.plant_name               AS entity_name,
       toInteger(pl.avg_downtime_hours * 10)
                                   AS score,
       ['avg_downtime: ' + toString(round(pl.avg_downtime_hours, 1)) + 'hrs/shift',
        'exceeds_4hr_threshold']   AS triggered_reasons,
       affected_products           AS affected_products,
       size(affected_products)     AS affected_count,
       pl.avg_downtime_hours       AS downtime_hours,
       pl.avg_machine_utilization_pct AS utilization_pct
ORDER BY pl.avg_downtime_hours DESC
"""

PLANT_LOW_ATTAINMENT = """
MATCH (pl:Plant)
WHERE pl.avg_production_attainment < 80.0
  AND pl.avg_production_attainment IS NOT NULL
OPTIONAL MATCH (pl)-[:PRODUCES]->(p:Product)
WITH pl, collect(DISTINCT p.product_name) AS affected_products
RETURN pl.plant_id                    AS entity_id,
       pl.plant_name                  AS entity_name,
       toInteger(80 - pl.avg_production_attainment)
                                      AS score,
       ['attainment: ' + toString(round(pl.avg_production_attainment,1)) + '%',
        'below_80pct_target']         AS triggered_reasons,
       affected_products              AS affected_products,
       size(affected_products)        AS affected_count,
       pl.avg_production_attainment   AS attainment_pct,
       pl.avg_defect_rate_pct         AS defect_rate_pct
ORDER BY pl.avg_production_attainment ASC
"""


# ═════════════════════════════════════════════════════════════════════════════
# WAREHOUSE QUERIES
# ═════════════════════════════════════════════════════════════════════════════

WAREHOUSE_STOCKOUT = """
MATCH (w:Warehouse)
WHERE w.health_flag = true
  AND w.stockout_sku_count > 0
OPTIONAL MATCH (w)-[st:STOCKS]->(p:Product)
WHERE st.stockout_flag = 1.0
WITH w, collect(DISTINCT p.product_name) AS stockout_products
RETURN w.warehouse_id              AS entity_id,
       w.warehouse_name            AS entity_name,
       (50 + w.stockout_sku_count * 10)
                                   AS score,
       [toString(w.stockout_sku_count) + '_skus_in_stockout',
        'capacity_status: ' + w.capacity_status]
                                   AS triggered_reasons,
       stockout_products           AS affected_products,
       w.stockout_sku_count        AS affected_count,
       w.utilization_pct           AS utilization_pct,
       w.is_bottleneck_warehouse   AS is_bottleneck,
       w.hub_tier                  AS hub_tier,
       w.region                    AS region
ORDER BY score DESC
"""

WAREHOUSE_OVER_CAPACITY = """
MATCH (w:Warehouse)
WHERE w.capacity_status = 'OVER_CAPACITY'
  AND w.utilization_pct > 95.0
OPTIONAL MATCH (w)-[:STOCKS]->(p:Product)
WITH w, collect(DISTINCT p.product_name) AS stocked_products
RETURN w.warehouse_id              AS entity_id,
       w.warehouse_name            AS entity_name,
       toInteger(w.utilization_pct)
                                   AS score,
       ['utilization: ' + toString(round(w.utilization_pct,1)) + '%',
        'above_95pct_capacity']    AS triggered_reasons,
       stocked_products            AS affected_products,
       size(stocked_products)      AS affected_count,
       w.utilization_pct           AS utilization_pct,
       w.storage_capacity_units    AS total_capacity,
       w.hub_tier                  AS hub_tier
ORDER BY w.utilization_pct DESC
"""

WAREHOUSE_BOTTLENECK = """
MATCH (w:Warehouse)
WHERE w.is_bottleneck_warehouse = true
OPTIONAL MATCH (w)-[st:STOCKS]->(p:Product)
WHERE st.stockout_flag = 1.0
WITH w, collect(DISTINCT p.product_name) AS bottleneck_products
RETURN w.warehouse_id              AS entity_id,
       w.warehouse_name            AS entity_name,
       (70 + w.bottleneck_product_count * 5)
                                   AS score,
       ['sole_stocking_point_for_' + toString(w.bottleneck_product_count) + '_product(s)',
        'hub_tier: ' + w.hub_tier] AS triggered_reasons,
       bottleneck_products         AS affected_products,
       w.bottleneck_product_count  AS affected_count,
       w.hub_tier                  AS hub_tier,
       w.region                    AS region
ORDER BY score DESC
"""

WAREHOUSE_BELOW_REORDER = """
MATCH (w:Warehouse)
WHERE w.below_reorder_sku_count > 0
OPTIONAL MATCH (w)-[st:STOCKS]->(p:Product)
WHERE st.stock_on_hand < st.reorder_point
WITH w, collect(DISTINCT p.product_name) AS at_risk_products
RETURN w.warehouse_id              AS entity_id,
       w.warehouse_name            AS entity_name,
       (30 + w.below_reorder_sku_count * 5)
                                   AS score,
       [toString(w.below_reorder_sku_count) + '_skus_below_reorder_point']
                                   AS triggered_reasons,
       at_risk_products            AS affected_products,
       w.below_reorder_sku_count   AS affected_count,
       w.stockout_sku_count        AS existing_stockouts,
       w.region                    AS region
ORDER BY score DESC
"""


# ═════════════════════════════════════════════════════════════════════════════
# CARRIER QUERIES
# ═════════════════════════════════════════════════════════════════════════════

CARRIER_UNDERPERFORMING = """
MATCH (ca:Carrier)
WHERE ca.carrier_risk_flag = true
  AND ca.network_on_time_pct < 75.0
  AND ca.network_on_time_pct IS NOT NULL
OPTIONAL MATCH (ca)-[:HANDLES_ROUTE]->(d:Destination)
WITH ca, collect(DISTINCT d.destination_name) AS affected_destinations
RETURN ca.carrier_id               AS entity_id,
       ca.carrier_name             AS entity_name,
       toInteger(100 - ca.network_on_time_pct)
                                   AS score,
       ['on_time_pct: ' + toString(round(ca.network_on_time_pct,1)) + '%',
        'below_75pct_threshold',
        'performance_tier: ' + ca.performance_tier]
                                   AS triggered_reasons,
       affected_destinations       AS affected_products,
       size(affected_destinations) AS affected_count,
       ca.network_on_time_pct      AS on_time_pct,
       ca.network_avg_delay_days   AS avg_delay_days,
       ca.carrier_type             AS carrier_type,
       ca.coverage_tier            AS coverage_tier
ORDER BY ca.network_on_time_pct ASC
"""

CARRIER_HIGH_DELAY = """
MATCH (ca:Carrier)
WHERE ca.network_avg_delay_days > 3.0
  AND ca.network_avg_delay_days IS NOT NULL
OPTIONAL MATCH (ca)-[:HANDLES_ROUTE]->(d:Destination)
WITH ca, collect(DISTINCT d.destination_name) AS affected_destinations
RETURN ca.carrier_id               AS entity_id,
       ca.carrier_name             AS entity_name,
       toInteger(ca.network_avg_delay_days * 10)
                                   AS score,
       ['avg_delay: ' + toString(round(ca.network_avg_delay_days,1)) + ' days',
        'exceeds_3day_threshold']  AS triggered_reasons,
       affected_destinations       AS affected_products,
       size(affected_destinations) AS affected_count,
       ca.network_avg_delay_days   AS avg_delay_days,
       ca.network_on_time_pct      AS on_time_pct
ORDER BY ca.network_avg_delay_days DESC
"""


# ═════════════════════════════════════════════════════════════════════════════
# CUSTOMER QUERIES
# ═════════════════════════════════════════════════════════════════════════════

CUSTOMER_VIP_AT_RISK = """
MATCH (c:Customer)
WHERE c.vip_at_risk_flag = true
OPTIONAL MATCH (c)-[d:DEMANDS]->(p:Product)
WHERE d.avg_fulfillment_rate_pct < 85.0
WITH c, collect(DISTINCT p.product_name) AS affected_products
RETURN c.customer_id               AS entity_id,
       c.customer_name             AS entity_name,
       toInteger(100 - c.avg_fulfillment_rate)
                                   AS score,
       ['vip_customer_at_risk',
        'fulfillment_rate: ' + toString(round(c.avg_fulfillment_rate,1)) + '%',
        'revenue_tier: ' + c.revenue_tier]
                                   AS triggered_reasons,
       affected_products           AS affected_products,
       size(affected_products)     AS affected_count,
       c.avg_fulfillment_rate      AS fulfillment_rate,
       c.total_revenue             AS total_revenue,
       c.revenue_tier              AS revenue_tier,
       c.channel                   AS channel
ORDER BY c.total_revenue DESC
"""

CUSTOMER_LOW_FULFILLMENT = """
MATCH (c:Customer)
WHERE c.fulfillment_risk_flag = true
  AND c.avg_fulfillment_rate < 70.0
  AND c.vip_at_risk_flag = false
OPTIONAL MATCH (c)-[d:DEMANDS]->(p:Product)
WHERE d.avg_fulfillment_rate_pct < 70.0
WITH c, collect(DISTINCT p.product_name) AS affected_products
RETURN c.customer_id               AS entity_id,
       c.customer_name             AS entity_name,
       toInteger(100 - c.avg_fulfillment_rate)
                                   AS score,
       ['fulfillment_rate: ' + toString(round(c.avg_fulfillment_rate,1)) + '%',
        'below_70pct_threshold']   AS triggered_reasons,
       affected_products           AS affected_products,
       size(affected_products)     AS affected_count,
       c.avg_fulfillment_rate      AS fulfillment_rate,
       c.customer_segment          AS segment
ORDER BY c.avg_fulfillment_rate ASC
"""


# ── Query registry ────────────────────────────────────────────────────────────
# Maps every anomaly_type to its detection Cypher query.
# anomaly_agent.py iterates this registry to run all detections.

ANOMALY_QUERY_REGISTRY = {
    # Vendor
    "VENDOR_CRITICAL_RISK":          VENDOR_CRITICAL_RISK,
    "VENDOR_HIGH_RISK":              VENDOR_HIGH_RISK,
    "VENDOR_UNDER_DELIVERY":         VENDOR_UNDER_DELIVERY,
    "VENDOR_SINGLE_SOURCE_CRITICAL": VENDOR_SINGLE_SOURCE_CRITICAL,
    # Product
    "PRODUCT_COMPOUNDED_RISK":       PRODUCT_COMPOUNDED_RISK,
    "PRODUCT_ACTIVE_STOCKOUT":       PRODUCT_ACTIVE_STOCKOUT,
    "PRODUCT_LOW_FULFILLMENT":       PRODUCT_LOW_FULFILLMENT,
    "PRODUCT_NO_VENDOR":             PRODUCT_NO_VENDOR,
    # Plant
    "PLANT_OVER_CAPACITY":           PLANT_OVER_CAPACITY,
    "PLANT_HIGH_DEFECT_RATE":        PLANT_HIGH_DEFECT_RATE,
    "PLANT_EXCESSIVE_DOWNTIME":      PLANT_EXCESSIVE_DOWNTIME,
    "PLANT_LOW_ATTAINMENT":          PLANT_LOW_ATTAINMENT,
    # Warehouse
    "WAREHOUSE_STOCKOUT":            WAREHOUSE_STOCKOUT,
    "WAREHOUSE_OVER_CAPACITY":       WAREHOUSE_OVER_CAPACITY,
    "WAREHOUSE_BOTTLENECK":          WAREHOUSE_BOTTLENECK,
    "WAREHOUSE_BELOW_REORDER":       WAREHOUSE_BELOW_REORDER,
    # Carrier
    "CARRIER_UNDERPERFORMING":       CARRIER_UNDERPERFORMING,
    "CARRIER_HIGH_DELAY":            CARRIER_HIGH_DELAY,
    # Customer
    "CUSTOMER_VIP_AT_RISK":          CUSTOMER_VIP_AT_RISK,
    "CUSTOMER_LOW_FULFILLMENT":      CUSTOMER_LOW_FULFILLMENT,
}
```

---

## Section 4 — Add Anomaly Narrative Prompt

Add this to your existing `agent/prompts.py`:

```python
# agent/prompts.py — ADD this block to the existing file

ANOMALY_NARRATIVE_PROMPT = """
You are a CPG supply chain analyst writing a concise alert summary.

The anomaly detection system has found the following issue:

Entity Type : {entity_type}
Entity Name : {entity_name}
Anomaly Type: {anomaly_type}
Severity    : {severity}
Score       : {score}/100
Reasons     : {triggered_reasons}
Affected    : {affected_products}

Write a 2-3 sentence business-friendly narrative that:
1. States clearly what the problem is and which entity is affected
2. Explains why it is significant using the reasons and affected products
3. Conveys the urgency based on severity (CRITICAL = immediate action,
   HIGH = action within 24hrs, MEDIUM = monitor and plan)

Do NOT use technical terms like 'node', 'graph', or 'Cypher'.
Do NOT suggest solutions — that is the Recommendation Agent's job.
Write in plain English as if briefing a supply chain manager.

Narrative:
"""
```

---

## Section 5 — The Anomaly Detection Agent

```python
# agent/anomaly_agent.py
# Core anomaly detection logic.
# Runs all Cypher queries from the registry, converts results into
# AnomalySignal objects, and optionally adds Claude-written narratives.

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.anomaly import AnomalySignal, ANOMALY_TYPE_REGISTRY
from agent.anomaly_queries import ANOMALY_QUERY_REGISTRY
from agent.prompts import ANOMALY_NARRATIVE_PROMPT

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = "neo4j"


# ── Neo4j driver ──────────────────────────────────────────────────────────────

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ── LLM for narrative generation only ────────────────────────────────────────

def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=300       # narratives are short — cap tokens
    )


# ── Anomaly ID generator ──────────────────────────────────────────────────────

def generate_anomaly_id() -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_id = str(uuid.uuid4())[:6].upper()
    return f"ANO-{date_str}-{short_id}"


# ── Row → AnomalySignal converter ────────────────────────────────────────────

def row_to_signal(
    row: Dict,
    anomaly_type: str,
    entity_type: str,
    severity: str
) -> AnomalySignal:
    """
    Converts a single Cypher result row into an AnomalySignal object.
    All Cypher queries must return entity_id, entity_name, score,
    triggered_reasons, affected_products, affected_count.
    Everything else goes into raw_data for downstream agents.
    """
    # Extract guaranteed columns
    entity_id   = str(row.get("entity_id", "unknown"))
    entity_name = str(row.get("entity_name", "unknown"))
    score       = min(100, max(0, int(row.get("score", 0))))

    triggered_reasons = row.get("triggered_reasons", [])
    if isinstance(triggered_reasons, str):
        triggered_reasons = [triggered_reasons]

    affected_products = row.get("affected_products", [])
    if isinstance(affected_products, str):
        affected_products = [affected_products]
    # Filter out None values that Neo4j can return
    affected_products = [p for p in affected_products if p is not None]

    affected_count = int(row.get("affected_count", len(affected_products)))

    # Everything else is raw_data for downstream agents
    raw_data = {k: v for k, v in row.items()
                if k not in {"entity_id", "entity_name", "score",
                             "triggered_reasons", "affected_products",
                             "affected_count"}}

    return AnomalySignal(
        anomaly_id        = generate_anomaly_id(),
        entity_type       = entity_type,
        entity_id         = entity_id,
        entity_name       = entity_name,
        anomaly_type      = anomaly_type,
        severity          = severity,
        score             = score,
        triggered_reasons = triggered_reasons,
        affected_products = affected_products,
        affected_count    = affected_count,
        detected_at       = datetime.now(timezone.utc).isoformat(),
        raw_data          = raw_data
    )


# ── Single anomaly type detector ─────────────────────────────────────────────

def detect_anomaly_type(
    driver,
    anomaly_type: str,
    cypher: str
) -> List[AnomalySignal]:
    """
    Runs one Cypher query and returns all AnomalySignal objects found.
    """
    registry_entry = ANOMALY_TYPE_REGISTRY.get(anomaly_type, {})
    entity_type    = registry_entry.get("entity_type", "Unknown")
    severity       = registry_entry.get("severity", "MEDIUM")

    signals = []
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            results = session.run(cypher)
            for row in results:
                signal = row_to_signal(
                    dict(row),
                    anomaly_type,
                    entity_type,
                    severity
                )
                signals.append(signal)
    except Exception as e:
        print(f"  ⚠️  Query failed for {anomaly_type}: {e}")

    return signals


# ── Narrative generation ──────────────────────────────────────────────────────

def add_narrative(signal: AnomalySignal, llm) -> AnomalySignal:
    """
    Calls Claude to write a 2-3 sentence business narrative for one signal.
    Returns the signal with narrative field populated.
    """
    prompt = PromptTemplate(
        input_variables=[
            "entity_type", "entity_name", "anomaly_type",
            "severity", "score", "triggered_reasons", "affected_products"
        ],
        template=ANOMALY_NARRATIVE_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        narrative = chain.invoke({
            "entity_type":       signal.entity_type,
            "entity_name":       signal.entity_name,
            "anomaly_type":      signal.anomaly_type,
            "severity":          signal.severity,
            "score":             signal.score,
            "triggered_reasons": ", ".join(signal.triggered_reasons),
            "affected_products": ", ".join(signal.affected_products[:5])
                                  or "N/A"
        })
        # Return a new signal with narrative set (Pydantic models are immutable)
        return signal.model_copy(update={"narrative": narrative.strip()})
    except Exception as e:
        print(f"  ⚠️  Narrative generation failed for {signal.anomaly_id}: {e}")
        return signal


# ── Main detection run ────────────────────────────────────────────────────────

def run_anomaly_detection(
    anomaly_types:      Optional[List[str]] = None,
    severity_filter:    Optional[str]       = None,
    entity_type_filter: Optional[str]       = None,
    with_narratives:    bool                = True,
    max_signals:        int                 = 100
) -> Dict:
    """
    Runs the full anomaly detection sweep across the knowledge graph.

    Parameters:
      anomaly_types      : run only these types (default: all)
      severity_filter    : 'CRITICAL', 'HIGH', or 'MEDIUM' (default: all)
      entity_type_filter : 'Vendor', 'Product', 'Plant' etc (default: all)
      with_narratives    : call Claude to add narrative summaries (default: True)
      max_signals        : cap total signals returned (default: 100)

    Returns a dict with signals grouped by severity and summary stats.
    """
    print("\n" + "="*60)
    print("🔍 CPG Supply Chain — Anomaly Detection Run")
    print(f"   Started: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)

    # Determine which queries to run
    queries_to_run = {}
    for atype, cypher in ANOMALY_QUERY_REGISTRY.items():
        registry = ANOMALY_TYPE_REGISTRY.get(atype, {})

        # Apply filters
        if anomaly_types and atype not in anomaly_types:
            continue
        if severity_filter and registry.get("severity") != severity_filter:
            continue
        if entity_type_filter and registry.get("entity_type") != entity_type_filter:
            continue

        queries_to_run[atype] = cypher

    print(f"\n   Running {len(queries_to_run)} detection queries...\n")

    # Run all detection queries
    driver      = get_driver()
    all_signals = []

    try:
        for anomaly_type, cypher in queries_to_run.items():
            signals = detect_anomaly_type(driver, anomaly_type, cypher)
            if signals:
                print(f"  ✅ {anomaly_type}: {len(signals)} anomaly(ies) found")
            else:
                print(f"  ⬜ {anomaly_type}: none")
            all_signals.extend(signals)
    finally:
        driver.close()

    # Sort by severity then score — CRITICAL first
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    all_signals.sort(
        key=lambda s: (severity_order.get(s.severity, 9), -s.score)
    )

    # Cap results
    all_signals = all_signals[:max_signals]

    # Add Claude narratives if requested
    if with_narratives and all_signals:
        print(f"\n📝 Generating narratives for {len(all_signals)} signal(s)...")
        llm = get_llm()
        all_signals = [add_narrative(s, llm) for s in all_signals]

    # Build response summary
    critical = [s for s in all_signals if s.severity == "CRITICAL"]
    high     = [s for s in all_signals if s.severity == "HIGH"]
    medium   = [s for s in all_signals if s.severity == "MEDIUM"]

    summary = {
        "run_at":          datetime.now(timezone.utc).isoformat(),
        "total_anomalies": len(all_signals),
        "by_severity": {
            "CRITICAL": len(critical),
            "HIGH":     len(high),
            "MEDIUM":   len(medium),
        },
        "by_entity_type": {},
        "signals":         [s.model_dump() for s in all_signals],
        "critical_signals": [s.model_dump() for s in critical],
    }

    # Count by entity type
    for s in all_signals:
        summary["by_entity_type"][s.entity_type] = \
            summary["by_entity_type"].get(s.entity_type, 0) + 1

    print(f"\n{'='*60}")
    print(f"   Detection complete.")
    print(f"   CRITICAL: {len(critical)}  HIGH: {len(high)}  MEDIUM: {len(medium)}")
    print(f"   Total: {len(all_signals)} anomaly signal(s) emitted")
    print(f"{'='*60}\n")

    return summary
```

---

## Section 6 — Add API Endpoints

Add these to your existing `api/routes.py`:

```python
# api/routes.py — ADD these blocks to the existing file

from agent.anomaly_agent import run_anomaly_detection   # add to imports
from models.anomaly import ANOMALY_TYPE_REGISTRY        # add to imports


# ── Request / Response models ─────────────────────────────────────────────────

class AnomalyRunRequest(BaseModel):
    severity_filter:    Optional[str]       = None  # CRITICAL / HIGH / MEDIUM
    entity_type_filter: Optional[str]       = None  # Vendor / Product / Plant etc
    anomaly_types:      Optional[List[str]] = None  # specific types only
    with_narratives:    Optional[bool]      = True  # generate Claude narratives
    max_signals:        Optional[int]       = 100


class AnomalyRunResponse(BaseModel):
    run_at:           str
    total_anomalies:  int
    by_severity:      Dict[str, int]
    by_entity_type:   Dict[str, int]
    signals:          List[Dict]
    critical_signals: List[Dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/anomaly/detect", response_model=AnomalyRunResponse)
async def detect_anomalies(request: AnomalyRunRequest):
    """
    Runs the full anomaly detection sweep.
    Returns all detected anomaly signals sorted by severity then score.

    Examples:
      POST /anomaly/detect                              → all anomalies
      POST /anomaly/detect {"severity_filter":"CRITICAL"} → only CRITICAL
      POST /anomaly/detect {"entity_type_filter":"Vendor"} → vendors only
      POST /anomaly/detect {"with_narratives": false}   → fast, no LLM
    """
    result = run_anomaly_detection(
        anomaly_types      = request.anomaly_types,
        severity_filter    = request.severity_filter,
        entity_type_filter = request.entity_type_filter,
        with_narratives    = request.with_narratives,
        max_signals        = request.max_signals or 100
    )
    return AnomalyRunResponse(**result)


@router.get("/anomaly/types")
async def list_anomaly_types():
    """
    Returns all registered anomaly types with their severity and description.
    Useful for building filter UIs.
    """
    return {
        "total": len(ANOMALY_TYPE_REGISTRY),
        "types": ANOMALY_TYPE_REGISTRY
    }


@router.post("/anomaly/detect/critical")
async def detect_critical_only():
    """
    Shortcut endpoint — runs only CRITICAL severity detections.
    Faster for dashboards that need a quick health check.
    """
    result = run_anomaly_detection(
        severity_filter = "CRITICAL",
        with_narratives = True,
        max_signals     = 50
    )
    return result
```

---

## Section 7 — Test the Agent

### 7.1 — Quick test script

```python
# test_anomaly.py — run from terminal: python test_anomaly.py

from agent.anomaly_agent import run_anomaly_detection

print("\n── TEST 1: Full detection, no narratives (fast) ──")
result = run_anomaly_detection(with_narratives=False)
print(f"Total signals: {result['total_anomalies']}")
print(f"By severity:   {result['by_severity']}")
print(f"By entity:     {result['by_entity_type']}")

print("\n── TEST 2: CRITICAL only, with narratives ──")
result = run_anomaly_detection(
    severity_filter = "CRITICAL",
    with_narratives = True,
    max_signals     = 10
)
for signal in result["critical_signals"][:3]:
    print(f"\n  [{signal['severity']}] {signal['anomaly_type']}")
    print(f"  Entity : {signal['entity_name']}")
    print(f"  Score  : {signal['score']}/100")
    print(f"  Reasons: {signal['triggered_reasons']}")
    print(f"  Affected: {signal['affected_products'][:3]}")
    if signal.get("narrative"):
        print(f"  Narrative: {signal['narrative']}")

print("\n── TEST 3: Vendor anomalies only ──")
result = run_anomaly_detection(
    entity_type_filter = "Vendor",
    with_narratives    = False
)
for s in result["signals"][:5]:
    print(f"  {s['severity']:<10} {s['anomaly_type']:<35} {s['entity_name']}")

print("\n── TEST 4: Specific anomaly types ──")
result = run_anomaly_detection(
    anomaly_types   = ["WAREHOUSE_STOCKOUT", "PRODUCT_ACTIVE_STOCKOUT",
                       "VENDOR_SINGLE_SOURCE_CRITICAL"],
    with_narratives = True,
    max_signals     = 20
)
print(f"Stockout/single-source signals: {result['total_anomalies']}")
```

### 7.2 — Test via API

```bash
# Start the server
uvicorn main:app --reload --port 8000

# Run full detection
curl -X POST http://localhost:8000/api/v1/anomaly/detect \
  -H "Content-Type: application/json" \
  -d '{"with_narratives": true}'

# Critical only — fast
curl -X POST http://localhost:8000/api/v1/anomaly/detect/critical

# Vendor anomalies only
curl -X POST http://localhost:8000/api/v1/anomaly/detect \
  -H "Content-Type: application/json" \
  -d '{"entity_type_filter": "Vendor", "with_narratives": true}'

# No narratives — fastest response
curl -X POST http://localhost:8000/api/v1/anomaly/detect \
  -H "Content-Type: application/json" \
  -d '{"with_narratives": false}'
```

---

## Section 8 — Verify the Agent End to End

```
✅ python test_anomaly.py runs without errors
✅ TEST 1 returns total_anomalies > 0 (assuming your data has risk signals)
✅ TEST 2 CRITICAL signals have narrative field populated
✅ Each signal has: anomaly_id, entity_name, score, triggered_reasons
✅ /api/v1/anomaly/detect returns valid JSON
✅ /api/v1/anomaly/types returns all 20 registered anomaly types
✅ CRITICAL signals always appear before HIGH, HIGH before MEDIUM
✅ No signals have score > 100 or score < 0
```

If `total_anomalies = 0` on all tests, run this in the Aura console to
confirm Step 3 enrichment is present:

```cypher
// Quick sanity check
MATCH (v:Vendor) WHERE v.risk_flag = true RETURN count(v) AS risky_vendors;
MATCH (w:Warehouse) WHERE w.health_flag = true RETURN count(w) AS unhealthy_warehouses;
MATCH (p:Product) WHERE p.compounded_risk_flag = true RETURN count(p) AS compounded_risk_products;
```

If those return 0, Step 3 enrichment needs to be re-run before this agent
will detect anything.

---

## Summary: What You Have After Step 6A

```
NEW FILES:
  models/anomaly.py          ← AnomalySignal data model + type registry
  agent/anomaly_queries.py   ← 20 threshold-based Cypher detection queries
  agent/anomaly_agent.py     ← detection engine + Claude narrative writer

NEW ENDPOINTS:
  POST /api/v1/anomaly/detect          ← full sweep, configurable filters
  POST /api/v1/anomaly/detect/critical ← CRITICAL only, fast
  GET  /api/v1/anomaly/types           ← list all 20 anomaly types

DETECTION COVERAGE:
  Vendor    → CRITICAL_RISK, HIGH_RISK, UNDER_DELIVERY,
              SINGLE_SOURCE_CRITICAL
  Product   → COMPOUNDED_RISK, ACTIVE_STOCKOUT,
              LOW_FULFILLMENT, NO_VENDOR
  Plant     → OVER_CAPACITY, HIGH_DEFECT_RATE,
              EXCESSIVE_DOWNTIME, LOW_ATTAINMENT
  Warehouse → STOCKOUT, OVER_CAPACITY,
              BOTTLENECK, BELOW_REORDER
  Carrier   → UNDERPERFORMING, HIGH_DELAY
  Customer  → VIP_AT_RISK, LOW_FULFILLMENT

AGENT BEHAVIOUR:
  Detection  → Pure Cypher — deterministic, no LLM, auditable
  Narratives → Claude writes 2-3 sentence business summary per signal
  Output     → List of AnomalySignal objects sorted CRITICAL→HIGH→MEDIUM
  Filters    → by severity, entity_type, specific anomaly_types

FEEDS INTO:
  Step 6B — Root Cause Analysis Agent  (takes AnomalySignal as input)
  Step 6C — Impact Analysis Agent      (takes AnomalySignal as input)
  Step 6D — Recommendation Agent       (takes AnomalySignal as input)
```

---

## Next Step Preview — Step 6B: Root Cause Analysis Agent

Step 6B takes each `AnomalySignal` emitted here and traverses
**upstream** in the graph to find the root cause:

```
[AnomalySignal: WAREHOUSE_STOCKOUT at Memphis DC]
         ↓
  Which products are in stockout?
         ↓
  Who supplies those products?  ← SUPPLIES traversal
         ↓
  What is that vendor's risk profile?
         ↓
  Is there a plant producing those products
  with performance issues?      ← PRODUCES traversal
         ↓
RootCause: "Vendor X under-delivery + Plant Y downtime
            caused stockout at Memphis DC"
```

The Root Cause Agent uses **weighted scoring** across the upstream path —
not LLM reasoning — to rank causes by likelihood. Claude writes the final
explanation narrative only after the scoring is complete.
```
