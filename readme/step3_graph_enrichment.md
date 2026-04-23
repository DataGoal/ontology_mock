# Step 3: Graph Enrichment
## CPG Supply Chain Knowledge Graph — Risk Signals, Computed Properties & Graph Algorithms

> **What this step does:** After Step 2 your graph has raw data.
> Step 3 makes it **intelligent** — by computing risk flags, health scores,
> dependency signals, and centrality metrics directly inside Neo4j using Cypher.
> These enriched properties are what your AI agents will reason over.
> Everything in this step runs in **Neo4j Browser** only. No Databricks needed.

---

## Before You Start — Checklist

```
✅ Step 2 complete — all nodes and relationships loaded from Databricks
✅ Validated: MATCH (n) RETURN labels(n)[0], count(n) shows correct counts
✅ Validated: CALL db.schema.visualization() shows all 9 labels + 7 rel types
✅ Neo4j Desktop local instance is RUNNING
✅ APOC plugin is installed (from Step 1 Phase 9)
```

Verify APOC is ready:
```cypher
RETURN apoc.version();
// Must return a version string, not an error
```

---

## What "Enrichment" Means in a Graph Context

In Databricks you compute metrics in SQL and store them in Delta tables.
In Neo4j, enrichment means **writing new properties directly onto existing
nodes and relationships** using `SET`. Nothing new is created — existing
nodes get smarter.

```
Before enrichment:   (Vendor {reliability_score: 0.61, tier: 'Tier 2'})
After enrichment:    (Vendor {reliability_score: 0.61, tier: 'Tier 2',
                               risk_flag: true,
                               risk_level: 'HIGH',
                               risk_reasons: ['low_reliability','under_delivery'],
                               single_source_product_count: 3})
```

Your agents query `risk_flag = true` — no joins, no aggregations at query time.
The work is done once here, results stored on the node.

---

## Enrichment Categories in This Step

```
Section 1 — Vendor Risk Signals
Section 2 — Product Vulnerability Signals
Section 3 — Plant Performance Signals
Section 4 — Warehouse Health Signals
Section 5 — Carrier Reliability Signals
Section 6 — Shipment Route Risk Signals
Section 7 — Customer Demand Risk Signals
Section 8 — Cross-Entity Composite Scoring
Section 9 — Centrality Signals via Pure Cypher (Aura compatible)
Section 10 — Verify All Enrichments
```

---

## Section 1 — Vendor Risk Signals

These signals answer: *"Which vendors should I be worried about?"*

### 1.1 — Flag low-reliability vendors

```cypher
// Vendors with reliability_score below threshold get risk_flag = true
// Thresholds based on CPG industry standard benchmarks:
//   < 0.75 = at-risk, < 0.60 = critical

MATCH (v:Vendor)
SET v.reliability_tier =
    CASE
        WHEN v.reliability_score >= 0.90 THEN 'EXCELLENT'
        WHEN v.reliability_score >= 0.75 THEN 'GOOD'
        WHEN v.reliability_score >= 0.60 THEN 'AT_RISK'
        ELSE 'CRITICAL'
    END;
```

### 1.2 — Flag vendors with chronic under-delivery

```cypher
// Look at the SUPPLIES relationship property we loaded in Step 2
// avg_delivery_variance_pct < -10 means consistently delivering 10%+ less than ordered

MATCH (v:Vendor)-[s:SUPPLIES]->(:Product)
WITH v,
     avg(s.avg_delivery_variance_pct)  AS overall_variance,
     avg(s.avg_lead_time_days)         AS overall_lead_time,
     sum(s.total_orders)               AS lifetime_orders,
     sum(s.total_spend)                AS lifetime_spend
SET v.overall_delivery_variance_pct = round(overall_variance, 2),
    v.overall_avg_lead_time_days     = round(overall_lead_time, 2),
    v.lifetime_orders                = toInteger(lifetime_orders),
    v.lifetime_spend                 = round(lifetime_spend, 2),
    v.under_delivery_flag            = (overall_variance < -10.0);
```

### 1.3 — Compute vendor composite risk score + risk reasons list

```cypher
// Composite risk score combines multiple signals into a single 0-100 score
// Higher score = higher risk
// risk_reasons is a list so agents can explain WHY a vendor is flagged

MATCH (v:Vendor)
WITH v,
     // Build a list of triggered risk reasons
     [reason IN [
         CASE WHEN v.reliability_tier IN ['AT_RISK','CRITICAL']
              THEN 'low_reliability' ELSE null END,
         CASE WHEN v.under_delivery_flag = true
              THEN 'chronic_under_delivery' ELSE null END,
         CASE WHEN v.overall_avg_lead_time_days > 45.0
              THEN 'excessive_lead_time' ELSE null END,
         CASE WHEN v.tier = 'Tier 3'
              THEN 'low_strategic_tier' ELSE null END,
         CASE WHEN v.active = false
              THEN 'inactive_vendor' ELSE null END
     ] WHERE reason IS NOT NULL] AS risk_reasons,
     // Score: each triggered reason adds weight
     (CASE WHEN v.reliability_tier = 'CRITICAL'   THEN 40 ELSE 0 END +
      CASE WHEN v.reliability_tier = 'AT_RISK'    THEN 20 ELSE 0 END +
      CASE WHEN v.under_delivery_flag = true       THEN 25 ELSE 0 END +
      CASE WHEN v.overall_avg_lead_time_days > 45  THEN 15 ELSE 0 END +
      CASE WHEN v.tier = 'Tier 3'                  THEN 10 ELSE 0 END) AS raw_score
SET v.risk_score   = toInteger(CASE WHEN raw_score > 100 THEN 100 ELSE raw_score END),
    v.risk_reasons = risk_reasons,
    v.risk_flag    = (size(risk_reasons) > 0);
```

### 1.4 — Count how many products each vendor uniquely supplies (dependency)

```cypher
// If a vendor is the ONLY supplier for a product, that product is single-sourced
// This is a critical supply chain risk signal

MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WITH v, count(p) AS products_supplied
SET v.products_supplied_count = toInteger(products_supplied);

// Now find how many of those products have only ONE vendor
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WITH p, collect(v.vendor_id) AS supplying_vendors
WHERE size(supplying_vendors) = 1
WITH supplying_vendors[0] AS sole_vendor_id
MATCH (v:Vendor {vendor_id: sole_vendor_id})
WITH v, count(*) AS single_source_count
SET v.single_source_product_count = toInteger(single_source_count);

// Set 0 for vendors who don't single-source anything
MATCH (v:Vendor)
WHERE v.single_source_product_count IS NULL
SET v.single_source_product_count = 0;
```

---

## Section 2 — Product Vulnerability Signals

These signals answer: *"Which products are most exposed to supply chain disruption?"*

### 2.1 — Single-source risk flag on Product nodes

```cypher
// A product supplied by only 1 vendor is critically exposed
// If that vendor fails, there is NO fallback

MATCH (p:Product)
OPTIONAL MATCH (v:Vendor)-[:SUPPLIES]->(p)
WITH p, count(v) AS vendor_count
SET p.vendor_count        = toInteger(vendor_count),
    p.single_source_risk  = (vendor_count <= 1),
    p.supply_diversity    =
        CASE
            WHEN vendor_count = 0 THEN 'NO_SUPPLY'
            WHEN vendor_count = 1 THEN 'SINGLE_SOURCE'
            WHEN vendor_count <= 3 THEN 'LOW_DIVERSITY'
            ELSE 'WELL_DIVERSIFIED'
        END;
```

### 2.2 — Stockout exposure flag

```cypher
// Check if any warehouse holding this product has a stockout flag

MATCH (p:Product)
OPTIONAL MATCH (w:Warehouse)-[st:STOCKS]->(p)
WITH p,
     count(w)                                AS warehouses_stocking,
     sum(st.stock_on_hand)                   AS total_stock_network,
     sum(CASE WHEN st.stockout_flag = 1.0
              THEN 1 ELSE 0 END)             AS stockout_warehouse_count,
     sum(CASE WHEN st.overstock_flag = 1.0
              THEN 1 ELSE 0 END)             AS overstock_warehouse_count,
     avg(st.stock_on_hand)                   AS avg_stock_per_warehouse
SET p.warehouses_stocking         = toInteger(warehouses_stocking),
    p.total_network_stock         = round(coalesce(total_stock_network, 0.0), 2),
    p.stockout_warehouse_count    = toInteger(coalesce(stockout_warehouse_count, 0)),
    p.overstock_warehouse_count   = toInteger(coalesce(overstock_warehouse_count, 0)),
    p.avg_stock_per_warehouse     = round(coalesce(avg_stock_per_warehouse, 0.0), 2),
    p.has_any_stockout            = (coalesce(stockout_warehouse_count, 0) > 0),
    p.has_any_overstock           = (coalesce(overstock_warehouse_count, 0) > 0);
```

### 2.3 — Demand pressure flag

```cypher
// Products with low fulfillment rate are under demand pressure

MATCH (p:Product)
OPTIONAL MATCH (c:Customer)-[d:DEMANDS]->(p)
WITH p,
     sum(d.total_units_demanded)         AS total_demand,
     sum(d.total_units_fulfilled)        AS total_fulfilled,
     avg(d.avg_fulfillment_rate_pct)     AS avg_fulfillment_rate,
     sum(d.total_revenue)                AS total_revenue,
     count(c)                            AS customer_count
SET p.total_demand            = round(coalesce(total_demand, 0.0), 2),
    p.total_fulfilled         = round(coalesce(total_fulfilled, 0.0), 2),
    p.avg_fulfillment_rate    = round(coalesce(avg_fulfillment_rate, 0.0), 2),
    p.total_revenue           = round(coalesce(total_revenue, 0.0), 2),
    p.customer_count          = toInteger(coalesce(customer_count, 0)),
    p.demand_pressure_flag    = (coalesce(avg_fulfillment_rate, 100.0) < 85.0);
```

### 2.4 — Composite product vulnerability score

```cypher
MATCH (p:Product)
WITH p,
     [reason IN [
         CASE WHEN p.single_source_risk = true   THEN 'single_source_vendor'   ELSE null END,
         CASE WHEN p.has_any_stockout = true      THEN 'active_stockout'        ELSE null END,
         CASE WHEN p.demand_pressure_flag = true  THEN 'low_fulfillment_rate'   ELSE null END,
         CASE WHEN p.vendor_count = 0             THEN 'no_vendor_supply'       ELSE null END
     ] WHERE reason IS NOT NULL] AS vulnerability_reasons,
     (CASE WHEN p.single_source_risk = true   THEN 35 ELSE 0 END +
      CASE WHEN p.has_any_stockout = true      THEN 40 ELSE 0 END +
      CASE WHEN p.demand_pressure_flag = true  THEN 20 ELSE 0 END +
      CASE WHEN p.vendor_count = 0             THEN 50 ELSE 0 END) AS raw_score
SET p.vulnerability_score   = toInteger(CASE WHEN raw_score > 100 THEN 100 ELSE raw_score END),
    p.vulnerability_reasons = vulnerability_reasons,
    p.vulnerability_flag    = (size(vulnerability_reasons) > 0);
```

---

## Section 3 — Plant Performance Signals

These signals answer: *"Which plants are underperforming or at capacity risk?"*

### 3.1 — Compute plant-level performance from PRODUCES relationships

```cypher
MATCH (pl:Plant)-[r:PRODUCES]->(:Product)
WITH pl,
     avg(r.avg_machine_utilization_pct)  AS avg_utilization,
     avg(r.avg_defect_rate_pct)          AS avg_defect_rate,
     avg(r.avg_downtime_hours)           AS avg_downtime,
     avg(r.avg_attainment_pct)           AS avg_attainment,
     sum(r.total_units_produced)         AS total_units_produced,
     count(r)                            AS products_manufactured
SET pl.avg_machine_utilization_pct  = round(avg_utilization, 2),
    pl.avg_defect_rate_pct          = round(avg_defect_rate, 4),
    pl.avg_downtime_hours           = round(avg_downtime, 2),
    pl.avg_production_attainment    = round(avg_attainment, 2),
    pl.total_units_produced         = round(total_units_produced, 2),
    pl.products_manufactured_count  = toInteger(products_manufactured);
```

### 3.2 — Flag plants with performance issues

```cypher
MATCH (pl:Plant)
WITH pl,
     [reason IN [
         CASE WHEN pl.avg_machine_utilization_pct > 90.0
              THEN 'near_capacity' ELSE null END,
         CASE WHEN pl.avg_machine_utilization_pct < 40.0
              THEN 'underutilized' ELSE null END,
         CASE WHEN pl.avg_defect_rate_pct > 5.0
              THEN 'high_defect_rate' ELSE null END,
         CASE WHEN pl.avg_downtime_hours > 4.0
              THEN 'excessive_downtime' ELSE null END,
         CASE WHEN pl.avg_production_attainment < 80.0
              THEN 'low_attainment' ELSE null END
     ] WHERE reason IS NOT NULL] AS performance_issues,
     (CASE WHEN pl.avg_machine_utilization_pct > 90  THEN 30 ELSE 0 END +
      CASE WHEN pl.avg_defect_rate_pct > 5.0         THEN 35 ELSE 0 END +
      CASE WHEN pl.avg_downtime_hours > 4.0           THEN 25 ELSE 0 END +
      CASE WHEN pl.avg_production_attainment < 80.0   THEN 20 ELSE 0 END) AS raw_score
SET pl.performance_score    = toInteger(CASE WHEN raw_score > 100 THEN 100 ELSE raw_score END),
    pl.performance_issues   = performance_issues,
    pl.performance_flag     = (size(performance_issues) > 0),
    pl.utilization_status   =
        CASE
            WHEN pl.avg_machine_utilization_pct > 90 THEN 'OVER_CAPACITY'
            WHEN pl.avg_machine_utilization_pct > 70 THEN 'OPTIMAL'
            WHEN pl.avg_machine_utilization_pct > 40 THEN 'UNDERUTILIZED'
            ELSE 'CRITICALLY_UNDERUTILIZED'
        END;
```

---

## Section 4 — Warehouse Health Signals

These signals answer: *"Which warehouses have inventory health problems?"*

### 4.1 — Compute warehouse inventory health from STOCKS relationships

```cypher
MATCH (w:Warehouse)-[st:STOCKS]->(:Product)
WITH w,
     count(st)                                              AS products_stocked,
     sum(st.stock_on_hand)                                 AS total_stock,
     sum(CASE WHEN st.stockout_flag = 1.0 THEN 1 ELSE 0 END)    AS stockout_skus,
     sum(CASE WHEN st.overstock_flag = 1.0 THEN 1 ELSE 0 END)   AS overstock_skus,
     sum(CASE WHEN st.stock_on_hand < st.reorder_point
              THEN 1 ELSE 0 END)                           AS below_reorder_skus
SET w.products_stocked_count  = toInteger(products_stocked),
    w.total_stock_units        = round(total_stock, 2),
    w.stockout_sku_count       = toInteger(coalesce(stockout_skus, 0)),
    w.overstock_sku_count      = toInteger(coalesce(overstock_skus, 0)),
    w.below_reorder_sku_count  = toInteger(coalesce(below_reorder_skus, 0));
```

### 4.2 — Compute utilization rate and health flags

```cypher
MATCH (w:Warehouse)
WITH w,
     CASE WHEN w.storage_capacity_units > 0
          THEN round(w.total_stock_units / w.storage_capacity_units * 100, 2)
          ELSE 0.0 END AS utilization_pct
SET w.utilization_pct = utilization_pct,
    w.capacity_status =
        CASE
            WHEN utilization_pct > 95  THEN 'OVER_CAPACITY'
            WHEN utilization_pct > 75  THEN 'HIGH_UTILIZATION'
            WHEN utilization_pct > 40  THEN 'NORMAL'
            WHEN utilization_pct > 10  THEN 'LOW_UTILIZATION'
            ELSE 'NEAR_EMPTY'
        END,
    w.health_flag = (
        coalesce(w.stockout_sku_count, 0) > 0
        OR utilization_pct > 95
        OR coalesce(w.below_reorder_sku_count, 0) > 0
    );
```

### 4.3 — Compute outbound shipment performance per warehouse

```cypher
MATCH (w:Warehouse)-[sh:SHIPS_TO]->(:Destination)
WITH w,
     avg(sh.on_time_pct)           AS avg_on_time_pct,
     sum(sh.total_shipments)       AS total_outbound_shipments,
     avg(sh.avg_freight_cost)      AS avg_freight_cost,
     avg(sh.avg_delivery_variance_days) AS avg_delay_days
SET w.avg_outbound_on_time_pct      = round(coalesce(avg_on_time_pct, 0.0), 2),
    w.total_outbound_shipments      = toInteger(coalesce(total_outbound_shipments, 0)),
    w.avg_outbound_freight_cost     = round(coalesce(avg_freight_cost, 0.0), 2),
    w.avg_outbound_delay_days       = round(coalesce(avg_delay_days, 0.0), 2);
```

---

## Section 5 — Carrier Reliability Signals

These signals answer: *"Which carriers are underperforming on my routes?"*

```cypher
MATCH (ca:Carrier)-[hr:HANDLES_ROUTE]->(:Destination)
WITH ca,
     avg(hr.on_time_pct)        AS network_on_time_pct,
     avg(hr.avg_transit_days)   AS network_avg_transit,
     avg(hr.avg_freight_cost)   AS network_avg_cost,
     sum(hr.total_shipments)    AS network_total_shipments,
     avg(hr.avg_delay_days)     AS network_avg_delay,
     count(hr)                  AS routes_covered
SET ca.network_on_time_pct         = round(coalesce(network_on_time_pct, 0.0), 2),
    ca.network_avg_transit_days    = round(coalesce(network_avg_transit, 0.0), 2),
    ca.network_avg_freight_cost    = round(coalesce(network_avg_cost, 0.0), 2),
    ca.network_total_shipments     = toInteger(coalesce(network_total_shipments, 0)),
    ca.network_avg_delay_days      = round(coalesce(network_avg_delay, 0.0), 2),
    ca.routes_covered_count        = toInteger(routes_covered),
    ca.performance_tier            =
        CASE
            WHEN coalesce(network_on_time_pct, 0) >= 95 THEN 'PREMIUM'
            WHEN coalesce(network_on_time_pct, 0) >= 85 THEN 'STANDARD'
            WHEN coalesce(network_on_time_pct, 0) >= 70 THEN 'AT_RISK'
            ELSE 'UNDERPERFORMING'
        END,
    ca.carrier_risk_flag = (coalesce(network_on_time_pct, 0) < 85.0
                            OR coalesce(network_avg_delay, 0) > 3.0);
```

---

## Section 6 — Shipment Route Risk Signals

These signals answer: *"Which routes are consistently delayed or expensive?"*

```cypher
// Enrich SHIPS_TO relationships with risk classification
MATCH (w:Warehouse)-[sh:SHIPS_TO]->(d:Destination)
SET sh.route_risk_level =
        CASE
            WHEN sh.avg_delivery_variance_days > 5.0  THEN 'HIGH_RISK'
            WHEN sh.avg_delivery_variance_days > 2.0  THEN 'MEDIUM_RISK'
            WHEN sh.avg_delivery_variance_days > 0.0  THEN 'LOW_RISK'
            ELSE 'ON_TIME'
        END,
    sh.cost_efficiency =
        CASE
            WHEN sh.avg_freight_cost > 50000  THEN 'EXPENSIVE'
            WHEN sh.avg_freight_cost > 10000  THEN 'MODERATE'
            ELSE 'EFFICIENT'
        END,
    sh.route_flag = (sh.avg_delivery_variance_days > 2.0
                     OR sh.on_time_pct < 80.0);
```

---

## Section 7 — Customer Demand Risk Signals

These signals answer: *"Which customers are at risk of being under-served?"*

### 7.1 — Customer-level fulfillment health

```cypher
MATCH (c:Customer)-[d:DEMANDS]->(:Product)
WITH c,
     avg(d.avg_fulfillment_rate_pct)     AS avg_fulfillment,
     sum(d.total_revenue)                AS total_revenue,
     sum(d.total_orders)                 AS total_orders,
     count(d)                            AS products_ordered,
     sum(d.total_units_demanded)         AS total_units_demanded,
     sum(d.total_units_fulfilled)        AS total_units_fulfilled
SET c.avg_fulfillment_rate    = round(coalesce(avg_fulfillment, 0.0), 2),
    c.total_revenue           = round(coalesce(total_revenue, 0.0), 2),
    c.total_orders            = toInteger(coalesce(total_orders, 0)),
    c.products_ordered_count  = toInteger(products_ordered),
    c.total_units_demanded    = round(coalesce(total_units_demanded, 0.0), 2),
    c.total_units_fulfilled   = round(coalesce(total_units_fulfilled, 0.0), 2),
    c.fulfillment_risk_flag   = (coalesce(avg_fulfillment, 100.0) < 85.0),
    c.fulfillment_tier        =
        CASE
            WHEN coalesce(avg_fulfillment, 0) >= 95 THEN 'EXCELLENT'
            WHEN coalesce(avg_fulfillment, 0) >= 85 THEN 'GOOD'
            WHEN coalesce(avg_fulfillment, 0) >= 70 THEN 'AT_RISK'
            ELSE 'CRITICAL'
        END;
```

### 7.2 — Flag high-value customers with fulfillment risk (VIP at risk)

```cypher
// Customers with high revenue but low fulfillment = highest business priority
MATCH (c:Customer)
WHERE c.total_revenue IS NOT NULL
WITH c,
     percentileCont(c.total_revenue, 0.75)
         OVER () AS revenue_p75
// Note: Neo4j doesn't support window functions the same way.
// Use this pattern instead:
RETURN 1; // placeholder — use the next query below
```

```cypher
// Correct pattern: compute percentile separately first
MATCH (c:Customer)
WHERE c.total_revenue IS NOT NULL
WITH percentileCont(collect(c.total_revenue), 0.75) AS revenue_p75
MATCH (c:Customer)
SET c.is_high_value      = (c.total_revenue >= revenue_p75),
    c.vip_at_risk_flag   = (c.total_revenue >= revenue_p75
                             AND c.fulfillment_risk_flag = true);
```

---

## Section 8 — Cross-Entity Composite Signals

These are the most powerful signals — they **propagate risk across the graph**.

### 8.1 — Mark products at COMPOUNDED risk
(single source vendor + that vendor is also high risk)

```cypher
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WHERE v.risk_flag = true
  AND p.single_source_risk = true
SET p.compounded_risk_flag   = true,
    p.compounded_risk_reason = 'sole_vendor_is_high_risk';

// Set false for all others
MATCH (p:Product)
WHERE p.compounded_risk_flag IS NULL
SET p.compounded_risk_flag = false;
```

### 8.2 — Propagate stockout risk upstream to vendor

```cypher
// If a warehouse has a stockout and the product is single-sourced,
// the responsible vendor should be flagged for escalation

MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)<-[st:STOCKS]-(w:Warehouse)
WHERE st.stockout_flag = 1.0
  AND p.single_source_risk = true
WITH v, count(p) AS stockout_products_count
SET v.linked_stockout_count      = toInteger(stockout_products_count),
    v.stockout_escalation_flag   = (stockout_products_count > 0);

MATCH (v:Vendor)
WHERE v.stockout_escalation_flag IS NULL
SET v.stockout_escalation_flag = false,
    v.linked_stockout_count    = 0;
```

### 8.3 — Identify supply chain bottleneck nodes

```cypher
// A warehouse is a bottleneck if:
// - It is the ONLY warehouse stocking a product that has demand
// AND the product has a stockout

MATCH (p:Product)<-[:STOCKS]-(w:Warehouse)
WHERE p.has_any_stockout = true
WITH p, collect(w.warehouse_id) AS stocking_warehouses
WHERE size(stocking_warehouses) = 1
MATCH (w:Warehouse {warehouse_id: stocking_warehouses[0]})
WITH w, count(p) AS bottleneck_products
SET w.is_bottleneck_warehouse    = true,
    w.bottleneck_product_count   = toInteger(bottleneck_products);

MATCH (w:Warehouse)
WHERE w.is_bottleneck_warehouse IS NULL
SET w.is_bottleneck_warehouse  = false,
    w.bottleneck_product_count = 0;
```

### 8.4 — Score ALTERNATIVE_FOR relationships with actionability

```cypher
// Make the vendor rebalancing recommendation more precise
// An alternative vendor is ACTIONABLE if:
// - It is active
// - Its reliability is higher than the at-risk vendor
// - It has capacity (shared_product_count > 0)

MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v_risk:Vendor)
WHERE v_risk.risk_flag = true
SET a.is_actionable_alternative =
        (v_alt.active = true
         AND v_alt.reliability_score > v_risk.reliability_score
         AND a.shared_product_count > 0),
    a.recommendation_priority =
        CASE
            WHEN v_alt.reliability_score > v_risk.reliability_score + 0.15
             AND a.cost_delta <= 0
             AND v_alt.active = true   THEN 'HIGH'
            WHEN v_alt.reliability_score > v_risk.reliability_score
             AND v_alt.active = true   THEN 'MEDIUM'
            ELSE 'LOW'
        END;
```

---

## Section 9 — Centrality Signals via Pure Cypher
### (Aura Free Tier compatible — no GDS required)

> **Why no GDS?** Neo4j Aura Free Tier does not support the Graph Data Science
> plugin. The queries below replicate the same intelligence — degree centrality,
> network criticality, and supply chain importance scoring — using only
> standard Cypher aggregation. The results written to nodes are identical
> in meaning to what GDS would produce.

---

### 9.1 — Degree Centrality for Vendor nodes
**What GDS did:** `gds.degree.write` counted incoming + outgoing relationships per vendor.
**What we do:** Count all relationships manually using Cypher `size()`.

```cypher
// Count every type of connection a Vendor has in the graph
// More connections = more central = higher disruption impact if it fails

MATCH (v:Vendor)
// Count products this vendor supplies
OPTIONAL MATCH (v)-[:SUPPLIES]->(p:Product)
WITH v, count(p) AS supplies_count

// Count how many other vendors this vendor is an alternative for
OPTIONAL MATCH (v)-[:ALTERNATIVE_FOR]->(v2:Vendor)
WITH v, supplies_count, count(v2) AS alt_for_count

// Count how many vendors consider this vendor as their alternative
OPTIONAL MATCH (v3:Vendor)-[:ALTERNATIVE_FOR]->(v)
WITH v, supplies_count, alt_for_count, count(v3) AS alternatives_count

// Total degree = sum of all relationship counts
WITH v,
     supplies_count,
     alt_for_count,
     alternatives_count,
     (supplies_count + alt_for_count + alternatives_count) AS total_degree

SET v.degree_centrality          = toInteger(total_degree),
    v.supplies_product_count     = toInteger(supplies_count),
    v.alternative_for_count      = toInteger(alt_for_count),
    v.has_alternatives_count     = toInteger(alternatives_count);
```

```cypher
// Classify vendors into centrality tiers based on relative degree
// Two-pass pattern: first get max, then classify all vendors

MATCH (v:Vendor)
WHERE v.degree_centrality IS NOT NULL
WITH max(v.degree_centrality) AS max_degree

MATCH (v:Vendor)
WHERE v.degree_centrality IS NOT NULL
SET v.supply_centrality =
    CASE
        WHEN v.degree_centrality >= max_degree * 0.75 THEN 'HIGH_IMPACT'
        WHEN v.degree_centrality >= max_degree * 0.40 THEN 'MEDIUM_IMPACT'
        ELSE 'LOW_IMPACT'
    END;
```

---

### 9.2 — Network Criticality for Product nodes
**What GDS did:** PageRank scored products by how many important nodes connect to them.
**What we do:** Count ALL unique entity types connected to each product — more connection
types = more of the supply chain depends on this product = higher criticality.

```cypher
// For each product, count how many distinct entities of each type touch it
// A product touched by many vendors + plants + warehouses + customers
// is deeply embedded in the supply chain = critical

MATCH (p:Product)

// Count vendors supplying this product
OPTIONAL MATCH (v:Vendor)-[:SUPPLIES]->(p)
WITH p, count(DISTINCT v) AS vendor_count_check

// Count plants producing this product
OPTIONAL MATCH (pl:Plant)-[:PRODUCES]->(p)
WITH p, vendor_count_check, count(DISTINCT pl) AS plant_count

// Count warehouses stocking this product
OPTIONAL MATCH (w:Warehouse)-[:STOCKS]->(p)
WITH p, vendor_count_check, plant_count, count(DISTINCT w) AS warehouse_count

// Count customers demanding this product
OPTIONAL MATCH (c:Customer)-[:DEMANDS]->(p)
WITH p, vendor_count_check, plant_count, warehouse_count,
     count(DISTINCT c) AS customer_count

// Weighted connectivity score:
// Customers weighted highest (revenue impact)
// Warehouses next (inventory exposure)
// Vendors and plants equal (supply risk)
WITH p,
     vendor_count_check,
     plant_count,
     warehouse_count,
     customer_count,
     (vendor_count_check * 2 +
      plant_count        * 2 +
      warehouse_count    * 3 +
      customer_count     * 4)    AS connectivity_score

SET p.vendor_connections    = toInteger(vendor_count_check),
    p.plant_connections     = toInteger(plant_count),
    p.warehouse_connections = toInteger(warehouse_count),
    p.customer_connections  = toInteger(customer_count),
    p.connectivity_score    = toInteger(connectivity_score);
```

```cypher
// Classify products into network criticality tiers
// Two-pass pattern: compute max first, then classify

MATCH (p:Product)
WHERE p.connectivity_score IS NOT NULL
WITH max(p.connectivity_score) AS max_score

MATCH (p:Product)
WHERE p.connectivity_score IS NOT NULL
SET p.network_criticality =
    CASE
        WHEN p.connectivity_score >= max_score * 0.75 THEN 'CRITICAL'
        WHEN p.connectivity_score >= max_score * 0.40 THEN 'HIGH'
        WHEN p.connectivity_score >= max_score * 0.15 THEN 'MEDIUM'
        ELSE 'LOW'
    END;
```

---

### 9.3 — Warehouse Network Importance Score

```cypher
// Warehouses that stock many products AND ship to many destinations
// are network hubs — their failure has cascading impact

MATCH (w:Warehouse)

OPTIONAL MATCH (w)-[:STOCKS]->(p:Product)
WITH w, count(DISTINCT p) AS stocked_products

OPTIONAL MATCH (w)-[:SHIPS_TO]->(d:Destination)
WITH w, stocked_products, count(DISTINCT d) AS destinations_served

WITH w,
     stocked_products,
     destinations_served,
     (stocked_products * 2 + destinations_served * 3) AS hub_score

SET w.stocked_product_count  = toInteger(stocked_products),
    w.destinations_served    = toInteger(destinations_served),
    w.hub_score              = toInteger(hub_score);
```

```cypher
// Classify warehouses into hub tiers
MATCH (w:Warehouse)
WHERE w.hub_score IS NOT NULL
WITH max(w.hub_score) AS max_hub

MATCH (w:Warehouse)
WHERE w.hub_score IS NOT NULL
SET w.hub_tier =
    CASE
        WHEN w.hub_score >= max_hub * 0.75 THEN 'MAJOR_HUB'
        WHEN w.hub_score >= max_hub * 0.40 THEN 'REGIONAL_HUB'
        ELSE 'LOCAL_WAREHOUSE'
    END;
```

---

### 9.4 — Customer Revenue Importance Score

```cypher
// Rank customers by revenue contribution relative to the network
// Used to prioritize which customers get served first during shortages

MATCH (c:Customer)
WHERE c.total_revenue IS NOT NULL
WITH max(c.total_revenue)  AS max_rev,
     min(c.total_revenue)  AS min_rev,
     avg(c.total_revenue)  AS avg_rev

MATCH (c:Customer)
WHERE c.total_revenue IS NOT NULL
// Normalize revenue to 0-100 scale
WITH c,
     max_rev, min_rev, avg_rev,
     CASE
         WHEN (max_rev - min_rev) > 0
         THEN round((c.total_revenue - min_rev) / (max_rev - min_rev) * 100, 2)
         ELSE 50.0
     END AS revenue_percentile_score

SET c.revenue_percentile_score = revenue_percentile_score,
    c.revenue_tier =
        CASE
            WHEN revenue_percentile_score >= 75 THEN 'TIER_1_KEY_ACCOUNT'
            WHEN revenue_percentile_score >= 40 THEN 'TIER_2_GROWTH'
            WHEN revenue_percentile_score >= 15 THEN 'TIER_3_STANDARD'
            ELSE 'TIER_4_SMALL'
        END,
    c.is_high_value    = (revenue_percentile_score >= 75),
    c.vip_at_risk_flag = (revenue_percentile_score >= 75
                          AND c.fulfillment_risk_flag = true);
```

---

### 9.5 — Carrier Network Coverage Score

```cypher
// Carriers that cover more routes and handle more shipments
// are more deeply integrated — harder to replace if they underperform

MATCH (ca:Carrier)

OPTIONAL MATCH (ca)-[:HANDLES_ROUTE]->(d:Destination)
WITH ca, count(DISTINCT d) AS destinations_covered

WITH ca,
     destinations_covered,
     coalesce(ca.network_total_shipments, 0)  AS total_shipments,
     (destinations_covered * 3 +
      toInteger(coalesce(ca.network_total_shipments, 0) / 100)) AS coverage_score

SET ca.destinations_covered = toInteger(destinations_covered),
    ca.coverage_score       = toInteger(coverage_score),
    ca.coverage_tier        =
        CASE
            WHEN destinations_covered >= 10 THEN 'STRATEGIC_CARRIER'
            WHEN destinations_covered >= 5  THEN 'REGIONAL_CARRIER'
            ELSE 'LOCAL_CARRIER'
        END;
```

---

## Section 10 — Verify All Enrichments

Run these in Neo4j Browser to confirm everything is working.

### 10.1 — See enriched properties on a sample Vendor

```cypher
MATCH (v:Vendor)
WHERE v.risk_flag = true
RETURN v.vendor_name,
       v.risk_score,
       v.risk_level,
       v.risk_reasons,
       v.reliability_tier,
       v.single_source_product_count,
       v.stockout_escalation_flag,
       v.supply_centrality
ORDER BY v.risk_score DESC
LIMIT 10;
```

### 10.2 — Most vulnerable products

```cypher
MATCH (p:Product)
WHERE p.vulnerability_flag = true
RETURN p.product_name,
       p.sku,
       p.vulnerability_score,
       p.vulnerability_reasons,
       p.single_source_risk,
       p.has_any_stockout,
       p.network_criticality
ORDER BY p.vulnerability_score DESC
LIMIT 10;
```

### 10.3 — Compounded risk path — the most dangerous situation

```cypher
// Show: high-risk vendor → single-sourced product → stockout warehouse
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)<-[st:STOCKS]-(w:Warehouse)
WHERE v.risk_flag = true
  AND p.single_source_risk = true
  AND st.stockout_flag = 1.0
RETURN v.vendor_name    AS vendor,
       v.risk_score     AS vendor_risk_score,
       p.product_name   AS product,
       w.warehouse_name AS warehouse_in_stockout
ORDER BY v.risk_score DESC;
```

### 10.4 — Actionable vendor alternatives

```cypher
// Show at-risk vendors and their actionable alternatives
MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v_risk:Vendor)
WHERE a.is_actionable_alternative = true
  AND v_risk.risk_flag = true
RETURN v_risk.vendor_name           AS at_risk_vendor,
       v_risk.risk_score            AS risk_score,
       v_alt.vendor_name            AS alternative_vendor,
       v_alt.reliability_score      AS alt_reliability,
       a.shared_product_count       AS shared_products,
       a.cost_delta                 AS cost_delta,
       a.recommendation_priority    AS priority
ORDER BY a.recommendation_priority, v_risk.risk_score DESC;
```

### 10.5 — Plant efficiency leaderboard

```cypher
MATCH (pl:Plant)
WHERE pl.avg_machine_utilization_pct IS NOT NULL
RETURN pl.plant_name,
       pl.utilization_status,
       pl.avg_machine_utilization_pct,
       pl.avg_defect_rate_pct,
       pl.avg_downtime_hours,
       pl.avg_production_attainment,
       pl.performance_flag,
       pl.performance_issues
ORDER BY pl.performance_score DESC;
```

### 10.6 — Warehouse health dashboard

```cypher
MATCH (w:Warehouse)
WHERE w.products_stocked_count IS NOT NULL
RETURN w.warehouse_name,
       w.capacity_status,
       w.utilization_pct,
       w.stockout_sku_count,
       w.overstock_sku_count,
       w.below_reorder_sku_count,
       w.health_flag,
       w.is_bottleneck_warehouse
ORDER BY w.stockout_sku_count DESC;
```

### 10.7 — Full property count per label (sanity check)

```cypher
// Confirms enrichment properties were written
MATCH (v:Vendor)   RETURN 'Vendor'   AS label, keys(v) AS properties LIMIT 1
UNION
MATCH (p:Product)  RETURN 'Product'  AS label, keys(p) AS properties LIMIT 1
UNION
MATCH (pl:Plant)   RETURN 'Plant'    AS label, keys(pl) AS properties LIMIT 1
UNION
MATCH (w:Warehouse) RETURN 'Warehouse' AS label, keys(w) AS properties LIMIT 1;
```

---

## Summary: What Your Graph Knows After Step 3

```
Vendor nodes now carry:
  reliability_tier              (EXCELLENT / GOOD / AT_RISK / CRITICAL)
  risk_score                    (0-100 composite)
  risk_flag                     (true/false)
  risk_reasons                  (list — explainable AI)
  single_source_product_count   (integer)
  under_delivery_flag           (true/false)
  overall_delivery_variance_pct (float)
  lifetime_orders               (integer)
  lifetime_spend                (float)
  degree_centrality             (integer — total graph connections)
  supply_centrality             (HIGH_IMPACT / MEDIUM_IMPACT / LOW_IMPACT)
  supplies_product_count        (integer)
  stockout_escalation_flag      (true/false)
  linked_stockout_count         (integer)

Product nodes now carry:
  vendor_count                  (supply diversity count)
  single_source_risk            (true/false)
  supply_diversity              (SINGLE_SOURCE / LOW / WELL_DIVERSIFIED)
  has_any_stockout              (true/false)
  has_any_overstock             (true/false)
  demand_pressure_flag          (true/false)
  vulnerability_score           (0-100 composite)
  vulnerability_reasons         (list — explainable AI)
  compounded_risk_flag          (true/false)
  connectivity_score            (integer — weighted connection count)
  network_criticality           (CRITICAL / HIGH / MEDIUM / LOW)
  vendor_connections            (integer)
  plant_connections             (integer)
  warehouse_connections         (integer)
  customer_connections          (integer)

Plant nodes now carry:
  utilization_status            (OVER_CAPACITY / OPTIMAL / UNDERUTILIZED)
  performance_score             (0-100)
  performance_flag              (true/false)
  performance_issues            (list — explainable AI)
  avg_machine_utilization_pct   (float)
  avg_defect_rate_pct           (float)
  avg_downtime_hours            (float)
  avg_production_attainment     (float)

Warehouse nodes now carry:
  capacity_status               (OVER_CAPACITY / NORMAL / NEAR_EMPTY)
  utilization_pct               (float)
  health_flag                   (true/false)
  stockout_sku_count            (integer)
  overstock_sku_count           (integer)
  below_reorder_sku_count       (integer)
  is_bottleneck_warehouse       (true/false)
  hub_score                     (integer — network importance)
  hub_tier                      (MAJOR_HUB / REGIONAL_HUB / LOCAL_WAREHOUSE)
  stocked_product_count         (integer)
  destinations_served           (integer)

Carrier nodes now carry:
  performance_tier              (PREMIUM / STANDARD / AT_RISK / UNDERPERFORMING)
  carrier_risk_flag             (true/false)
  network_on_time_pct           (float)
  network_avg_delay_days        (float)
  coverage_score                (integer)
  coverage_tier                 (STRATEGIC / REGIONAL / LOCAL)
  destinations_covered          (integer)

Customer nodes now carry:
  fulfillment_tier              (EXCELLENT / GOOD / AT_RISK / CRITICAL)
  fulfillment_risk_flag         (true/false)
  revenue_tier                  (TIER_1_KEY_ACCOUNT → TIER_4_SMALL)
  revenue_percentile_score      (0-100 normalized)
  is_high_value                 (true/false)
  vip_at_risk_flag              (true/false — highest priority alert)
  total_revenue                 (float)
  avg_fulfillment_rate          (float)

SHIPS_TO relationships now carry:
  route_risk_level              (HIGH_RISK / MEDIUM_RISK / LOW_RISK / ON_TIME)
  cost_efficiency               (EXPENSIVE / MODERATE / EFFICIENT)
  route_flag                    (true/false)

ALTERNATIVE_FOR relationships now carry:
  is_actionable_alternative     (true/false)
  recommendation_priority       (HIGH / MEDIUM / LOW)
```

---

## Next Step Preview — Step 4: AI Agent Integration

Your graph is now fully enriched and ready for agent queries.
Step 4 will cover:
- Setting up LangChain with Neo4j GraphCypherQAChain
- Building the system prompt using your ontology schema as context
- Wiring the chatbox natural language input → Cypher → graph answer
- Connecting to your Databricks metric views for hybrid queries
```
