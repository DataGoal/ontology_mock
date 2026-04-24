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