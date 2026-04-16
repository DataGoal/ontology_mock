-- =============================================================================
-- CPG Supply Chain – Sample Analytics Queries
-- Uses semantic views defined in 03_views_and_semantic_layer.sql
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. VENDOR SCORECARD
--    Rank vendors by reliability and delivery performance YTD
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  vendor_name,
  vendor_tier,
  vendor_region,
  COUNT(*)                                            AS total_pos,
  ROUND(SUM(total_cost), 2)                           AS total_spend,
  ROUND(AVG(lead_time_days), 1)                       AS avg_lead_time_days,
  ROUND(AVG(delivery_variance_pct), 2)                AS avg_delivery_variance_pct,
  ROUND(SUM(CASE WHEN delivery_performance = 'On-Target' THEN 1 ELSE 0 END)
        / COUNT(*) * 100, 1)                          AS pct_on_target,
  ROUND(SUM(CASE WHEN lead_time_performance = 'On-Time'  THEN 1 ELSE 0 END)
        / COUNT(*) * 100, 1)                          AS pct_on_time
FROM cpg_supply_chain.v_procurement_enriched
WHERE year = 2023
GROUP BY 1,2,3
ORDER BY total_spend DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. MANUFACTURING OEE TREND
--    Monthly attainment, defect rate, and downtime by plant and product category
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  year,
  month,
  month_name,
  plant_name,
  plant_region,
  category,
  ROUND(AVG(attainment_pct), 2)          AS avg_attainment_pct,
  ROUND(AVG(defect_rate_pct), 4)         AS avg_defect_rate_pct,
  ROUND(AVG(machine_utilization_pct), 2) AS avg_machine_util_pct,
  ROUND(SUM(downtime_hours), 1)          AS total_downtime_hours,
  ROUND(SUM(units_produced), 0)          AS total_units_produced
FROM cpg_supply_chain.v_manufacturing_enriched
WHERE year = 2023
GROUP BY 1,2,3,4,5,6
ORDER BY year, month, total_units_produced DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. INVENTORY HEALTH DASHBOARD
--    Current stockout and overstock exposure by warehouse and brand
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  warehouse_name,
  warehouse_region,
  brand,
  category,
  COUNT(*)                                            AS total_sku_snapshots,
  SUM(CASE WHEN inventory_health_status = 'Stockout'      THEN 1 ELSE 0 END) AS stockout_count,
  SUM(CASE WHEN inventory_health_status = 'Overstock'     THEN 1 ELSE 0 END) AS overstock_count,
  SUM(CASE WHEN inventory_health_status = 'Near-Stockout' THEN 1 ELSE 0 END) AS near_stockout_count,
  ROUND(SUM(CASE WHEN inventory_health_status = 'Stockout' THEN 1 ELSE 0 END)
        / COUNT(*) * 100, 2)                          AS stockout_rate_pct,
  ROUND(AVG(stock_coverage_ratio), 2)                 AS avg_stock_coverage_ratio
FROM cpg_supply_chain.v_inventory_health
WHERE year = 2023
GROUP BY 1,2,3,4
ORDER BY stockout_rate_pct DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. OTIF (On Time In Full) BY CARRIER AND LANE
--    Key logistics KPI: % of shipments delivered on time and in full
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  carrier_name,
  carrier_type,
  origin_country,
  destination_country,
  COUNT(*)                                             AS total_shipments,
  ROUND(SUM(otif_flag) / COUNT(*) * 100, 2)           AS otif_pct,
  carrier_otd_benchmark                               AS carrier_sla_otd_pct,
  ROUND(AVG(transit_days_actual), 1)                  AS avg_actual_transit_days,
  ROUND(AVG(transit_days_expected), 1)                AS avg_expected_transit_days,
  ROUND(AVG(delivery_variance_days), 2)               AS avg_delivery_variance_days,
  ROUND(AVG(freight_cost_per_unit), 4)                AS avg_freight_cost_per_unit
FROM cpg_supply_chain.v_shipment_performance
WHERE year = 2023
GROUP BY 1,2,3,4, carrier_otd_benchmark
ORDER BY otif_pct DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. TOP 10 REVENUE SKUs BY CUSTOMER SEGMENT
--    Identify power SKUs and key accounts for commercial planning
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  category,
  brand,
  sku,
  product_name,
  customer_segment,
  channel,
  ROUND(SUM(revenue), 2)                              AS total_revenue,
  SUM(units_demanded)                                 AS total_units_demanded,
  SUM(units_fulfilled)                                AS total_units_fulfilled,
  ROUND(AVG(fulfillment_rate_pct), 2)                 AS avg_fulfillment_rate_pct
FROM cpg_supply_chain.v_sales_demand_enriched
WHERE year = 2023
GROUP BY 1,2,3,4,5,6
ORDER BY total_revenue DESC
LIMIT 10;


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. END-TO-END SUPPLY CHAIN SCORECARD
--    Monthly KPIs across all five domains – procurement, mfg, inventory,
--    logistics, and demand – for executive reporting
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
  year,
  month,
  category,
  ROUND(total_revenue, 2)                             AS revenue,
  ROUND(total_procurement_cost, 2)                    AS procurement_cost,
  ROUND(total_revenue - total_procurement_cost, 2)    AS gross_margin_proxy,
  ROUND(avg_fulfillment_rate_pct, 2)                  AS fill_rate_pct,
  ROUND(avg_vendor_lead_time_days, 1)                 AS vendor_lead_time_days,
  ROUND(avg_vendor_delivery_variance_pct, 2)          AS vendor_delivery_variance_pct,
  ROUND(avg_machine_utilization_pct, 2)               AS machine_utilization_pct,
  ROUND(avg_defect_rate_pct, 4)                       AS defect_rate_pct,
  ROUND(total_downtime_hours, 1)                      AS downtime_hours
FROM cpg_supply_chain.v_monthly_sc_scorecard
WHERE year = 2023
ORDER BY year, month, revenue DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. DEMAND SEASONALITY ANALYSIS
--    Month-over-month demand index per category to identify seasonal patterns
-- ─────────────────────────────────────────────────────────────────────────────
WITH monthly_demand AS (
  SELECT
    year, month, month_name, category,
    SUM(units_demanded) AS monthly_units
  FROM cpg_supply_chain.v_sales_demand_enriched
  GROUP BY 1,2,3,4
),
annual_avg AS (
  SELECT
    year, category,
    AVG(monthly_units) AS avg_monthly_units
  FROM monthly_demand
  GROUP BY 1,2
)
SELECT
  md.year,
  md.month,
  md.month_name,
  md.category,
  ROUND(md.monthly_units, 0)                                                AS monthly_units,
  ROUND(aa.avg_monthly_units, 0)                                            AS annual_avg_monthly_units,
  ROUND(md.monthly_units / NULLIF(aa.avg_monthly_units, 0) * 100, 1)       AS seasonality_index
FROM monthly_demand md
JOIN annual_avg aa ON md.year = aa.year AND md.category = aa.category
ORDER BY md.year, md.category, md.month;


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. SUPPLIER CONCENTRATION RISK
--    Identify dependency on single vendors (Pareto / category exposure)
-- ─────────────────────────────────────────────────────────────────────────────
WITH vendor_spend AS (
  SELECT
    vendor_name,
    vendor_tier,
    vendor_region,
    category,
    ROUND(SUM(total_cost), 2)             AS vendor_category_spend
  FROM cpg_supply_chain.v_procurement_enriched
  WHERE year = 2023
  GROUP BY 1,2,3,4
),
category_total AS (
  SELECT category, SUM(vendor_category_spend) AS total_category_spend
  FROM vendor_spend
  GROUP BY 1
),
ranked AS (
  SELECT
    vs.*,
    ct.total_category_spend,
    ROUND(vs.vendor_category_spend / NULLIF(ct.total_category_spend, 0) * 100, 2) AS spend_share_pct,
    RANK() OVER (PARTITION BY vs.category ORDER BY vs.vendor_category_spend DESC) AS spend_rank
  FROM vendor_spend vs
  JOIN category_total ct ON vs.category = ct.category
)
SELECT *
FROM ranked
WHERE spend_rank <= 5
ORDER BY category, spend_rank;
