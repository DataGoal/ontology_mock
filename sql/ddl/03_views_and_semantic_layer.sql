-- =============================================================================
-- CPG Supply Chain Data Model
-- DDL: Views, Optimizations, and Semantic Layer
-- Compatible: Databricks Runtime 12.x+
-- =============================================================================

-- =============================================================================
-- DELTA LAKE OPTIMIZATIONS
-- Run after initial data load; re-run after large incremental loads.
-- =============================================================================

OPTIMIZE nike_databricks.cpg_supply_chain.dim_date;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_vendor;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_plant;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_shift;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_warehouse;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_carrier;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_product;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_customer;
OPTIMIZE nike_databricks.cpg_supply_chain.dim_destination;

OPTIMIZE nike_databricks.cpg_supply_chain.fact_procurement;
OPTIMIZE nike_databricks.cpg_supply_chain.fact_manufacturing;
OPTIMIZE nike_databricks.cpg_supply_chain.fact_inventory;
OPTIMIZE nike_databricks.cpg_supply_chain.fact_shipment;
OPTIMIZE nike_databricks.cpg_supply_chain.fact_sales_demand;

-- Z-Order on most common analytical join keys
OPTIMIZE nike_databricks.cpg_supply_chain.fact_procurement    ZORDER BY (vendor_id, product_id);
OPTIMIZE nike_databricks.cpg_supply_chain.fact_manufacturing  ZORDER BY (plant_id, product_id);
OPTIMIZE nike_databricks.cpg_supply_chain.fact_inventory      ZORDER BY (warehouse_id, product_id);
OPTIMIZE nike_databricks.cpg_supply_chain.fact_shipment       ZORDER BY (carrier_id, product_id);
OPTIMIZE nike_databricks.cpg_supply_chain.fact_sales_demand   ZORDER BY (customer_id, product_id);

-- Analyze tables for query statistics
ANALYZE TABLE nike_databricks.cpg_supply_chain.dim_product     COMPUTE STATISTICS FOR ALL COLUMNS;
ANALYZE TABLE nike_databricks.cpg_supply_chain.fact_sales_demand COMPUTE STATISTICS FOR ALL COLUMNS;

-- =============================================================================
-- SEMANTIC LAYER VIEWS
-- Pre-joined views for BI tools and Data Science teams.
-- =============================================================================

-- ── V_PROCUREMENT_ENRICHED ─────────────────────────────────────────────────
CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.v_procurement_enriched AS
SELECT
  fp.procurement_id,
  dd.full_date                          AS order_date,
  dd.year,
  dd.quarter,
  dd.month,
  dd.month_name,
  dv.vendor_name,
  dv.vendor_type,
  dv.tier                               AS vendor_tier,
  dv.country                            AS vendor_country,
  dv.region                             AS vendor_region,
  dv.reliability_score                  AS vendor_reliability_score,
  dp.sku,
  dp.product_name,
  dp.category,
  dp.sub_category,
  dp.brand,
  dw.warehouse_name,
  dw.type                               AS warehouse_type,
  dw.country                            AS warehouse_country,
  fp.quantity_ordered,
  fp.quantity_delivered,
  fp.delivery_variance_pct,
  fp.unit_cost,
  fp.total_cost,
  fp.lead_time_days,
  fp.status,
  -- Derived KPIs
  CASE WHEN fp.delivery_variance_pct < -5  THEN 'Under-delivery'
       WHEN fp.delivery_variance_pct >  5  THEN 'Over-delivery'
       ELSE 'On-Target' END              AS delivery_performance,
  CASE WHEN fp.lead_time_days > dv.avg_lead_time_days * 1.20 THEN 'Late'
       WHEN fp.lead_time_days < dv.avg_lead_time_days * 0.80 THEN 'Early'
       ELSE 'On-Time' END               AS lead_time_performance
FROM nike_databricks.cpg_supply_chain.fact_procurement fp
JOIN nike_databricks.cpg_supply_chain.dim_date        dd ON fp.date_id       = dd.date_id
JOIN nike_databricks.cpg_supply_chain.dim_vendor      dv ON fp.vendor_id     = dv.vendor_id
JOIN nike_databricks.cpg_supply_chain.dim_product     dp ON fp.product_id    = dp.product_id
JOIN nike_databricks.cpg_supply_chain.dim_warehouse   dw ON fp.warehouse_id  = dw.warehouse_id;


-- ── V_MANUFACTURING_ENRICHED ───────────────────────────────────────────────
CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.v_manufacturing_enriched AS
SELECT
  fm.manufacturing_id,
  dd.full_date                           AS production_date,
  dd.year,
  dd.quarter,
  dd.month,
  dd.month_name,
  dd.day_of_week,
  dp2.plant_name,
  dp2.plant_code,
  dp2.plant_type,
  dp2.country                            AS plant_country,
  dp2.region                             AS plant_region,
  dp.sku,
  dp.product_name,
  dp.category,
  dp.brand,
  ds.shift_name,
  ds.shift_supervisor,
  fm.units_planned,
  fm.units_produced,
  fm.defect_rate_pct,
  fm.throughput_rate,
  fm.machine_utilization_pct,
  fm.downtime_hours,
  -- OEE proxy
  ROUND(fm.units_produced / NULLIF(fm.units_planned, 0) * 100, 2) AS attainment_pct,
  -- Shift efficiency classification
  CASE WHEN fm.machine_utilization_pct >= 90 THEN 'High'
       WHEN fm.machine_utilization_pct >= 70 THEN 'Medium'
       ELSE 'Low' END                    AS utilization_band
FROM nike_databricks.cpg_supply_chain.fact_manufacturing fm
JOIN nike_databricks.cpg_supply_chain.dim_date     dd  ON fm.date_id    = dd.date_id
JOIN nike_databricks.cpg_supply_chain.dim_plant    dp2 ON fm.plant_id   = dp2.plant_id
JOIN nike_databricks.cpg_supply_chain.dim_product  dp  ON fm.product_id = dp.product_id
JOIN nike_databricks.cpg_supply_chain.dim_shift    ds  ON fm.shift_id   = ds.shift_id;

 ---- Metric View: inventory_health_metrics ----------------------

CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.mv_inventory_health_metrics
COMMENT 'Inventory health metric view'
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: nike_databricks.cpg_supply_chain.v_inventory_health
dimensions:
  - name: snapshot_date
    expr: snapshot_date
  - name: year
    expr: year
  - name: month
    expr: month
  - name: warehouse_name
    expr: warehouse_name
  - name: warehouse_type
    expr: warehouse_type
  - name: warehouse_country
    expr: warehouse_country
  - name: warehouse_region
    expr: warehouse_region
  - name: sku
    expr: sku
  - name: product_name
    expr: product_name
  - name: category
    expr: category
  - name: brand
    expr: brand
  - name: inventory_health_status
    expr: inventory_health_status
measures:
  - name: inventory_records
    expr: COUNT(1)
  - name: total_stock_on_hand
    expr: SUM(stock_on_hand)
  - name: total_safety_stock
    expr: SUM(safety_stock)
  - name: total_reorder_point
    expr: SUM(reorder_point)
  - name: stockout_count
    expr: SUM(stockout_flag)
  - name: overstock_count
    expr: SUM(overstock_flag)
  - name: avg_stock_coverage_ratio
    expr: AVG(stock_coverage_ratio)
$$;

-- ── V_INVENTORY_HEALTH ─────────────────────────────────────────────────────
CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.v_inventory_health AS
SELECT
  fi.inventory_id,
  dd.full_date                           AS snapshot_date,
  dd.year,
  dd.month,
  dd.month_name,
  dw.warehouse_name,
  dw.type                                AS warehouse_type,
  dw.country                             AS warehouse_country,
  dw.region                              AS warehouse_region,
  dp.sku,
  dp.product_name,
  dp.category,
  dp.brand,
  fi.stock_on_hand,
  fi.reorder_point,
  fi.safety_stock,
  fi.stockout_flag,
  fi.overstock_flag,
  -- Days of Supply (requires avg daily demand – approximated here)
  ROUND(fi.stock_on_hand / NULLIF(fi.reorder_point, 0), 2) AS stock_coverage_ratio,
  -- Health classification
  CASE WHEN fi.stockout_flag  = 1 THEN 'Stockout'
       WHEN fi.overstock_flag = 1 THEN 'Overstock'
       WHEN fi.stock_on_hand  < fi.safety_stock * 1.2 THEN 'Near-Stockout'
       ELSE 'Healthy' END               AS inventory_health_status
FROM nike_databricks.cpg_supply_chain.fact_inventory fi
JOIN nike_databricks.cpg_supply_chain.dim_date      dd ON fi.date_id      = dd.date_id
JOIN nike_databricks.cpg_supply_chain.dim_warehouse dw ON fi.warehouse_id = dw.warehouse_id
JOIN nike_databricks.cpg_supply_chain.dim_product   dp ON fi.product_id   = dp.product_id;


-- ── V_SHIPMENT_PERFORMANCE ─────────────────────────────────────────────────
CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.v_shipment_performance AS
SELECT
  fs.shipment_id,
  dd.full_date                           AS ship_date,
  dd.year,
  dd.quarter,
  dd.month,
  dc.carrier_name,
  dc.carrier_type,
  dc.on_time_delivery_pct                AS carrier_otd_benchmark,
  dp.sku,
  dp.product_name,
  dp.category,
  dp.brand,
  dw.warehouse_name                      AS origin_warehouse,
  dw.country                             AS origin_country,
  dw.region                              AS origin_region,
  ddest.destination_name,
  ddest.destination_type,
  ddest.country                          AS destination_country,
  ddest.region                           AS destination_region,
  fs.quantity_shipped,
  fs.quantity_received,
  ROUND((fs.quantity_received / NULLIF(fs.quantity_shipped,0)) * 100, 2) AS receipt_fill_rate_pct,
  fs.transit_days_actual,
  fs.transit_days_expected,
  fs.delivery_variance_days,
  fs.freight_cost,
  ROUND(fs.freight_cost / NULLIF(fs.quantity_shipped, 0), 4) AS freight_cost_per_unit,
  fs.shipment_status,
  -- OTIF flag
  CASE WHEN fs.delivery_variance_days <= 0
            AND fs.quantity_received >= fs.quantity_shipped * 0.98
       THEN 1 ELSE 0 END                AS otif_flag
FROM nike_databricks.cpg_supply_chain.fact_shipment     fs
JOIN nike_databricks.cpg_supply_chain.dim_date          dd    ON fs.date_id             = dd.date_id
JOIN nike_databricks.cpg_supply_chain.dim_carrier       dc    ON fs.carrier_id          = dc.carrier_id
JOIN nike_databricks.cpg_supply_chain.dim_product       dp    ON fs.product_id          = dp.product_id
JOIN nike_databricks.cpg_supply_chain.dim_warehouse     dw    ON fs.origin_warehouse_id = dw.warehouse_id
JOIN nike_databricks.cpg_supply_chain.dim_destination   ddest ON fs.destination_id      = ddest.destination_id;


-- ── V_SALES_DEMAND_ENRICHED ────────────────────────────────────────────────
CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.v_sales_demand_enriched AS
SELECT
  fsd.demand_id,
  dd.full_date                           AS order_date,
  dd.year,
  dd.quarter,
  dd.month,
  dd.month_name,
  dd.is_holiday,
  dp.sku,
  dp.product_name,
  dp.category,
  dp.sub_category,
  dp.brand,
  dc.customer_name,
  dc.customer_segment,
  dc.channel,
  dc.country                             AS customer_country,
  dc.region                              AS customer_region,
  ddest.destination_name,
  ddest.destination_type,
  ddest.country                          AS destination_country,
  ddest.region                           AS destination_region,
  fsd.units_demanded,
  fsd.units_fulfilled,
  fsd.fulfillment_rate_pct,
  fsd.revenue,
  ROUND(fsd.revenue / NULLIF(fsd.units_fulfilled, 0), 4) AS revenue_per_unit,
  -- Gap analysis
  fsd.units_demanded - fsd.units_fulfilled AS unfulfilled_units,
  -- Performance band
  CASE WHEN fsd.fulfillment_rate_pct >= 98 THEN 'Excellent'
       WHEN fsd.fulfillment_rate_pct >= 95 THEN 'Good'
       WHEN fsd.fulfillment_rate_pct >= 90 THEN 'Acceptable'
       ELSE 'Poor' END                   AS fulfillment_band
FROM nike_databricks.cpg_supply_chain.fact_sales_demand fsd
JOIN nike_databricks.cpg_supply_chain.dim_date          dd    ON fsd.date_id        = dd.date_id
JOIN nike_databricks.cpg_supply_chain.dim_product       dp    ON fsd.product_id     = dp.product_id
JOIN nike_databricks.cpg_supply_chain.dim_customer      dc    ON fsd.customer_id    = dc.customer_id
JOIN nike_databricks.cpg_supply_chain.dim_destination   ddest ON fsd.destination_id = ddest.destination_id;


-- =============================================================================
-- SUPPLY CHAIN SCORECARD VIEW (Cross-Domain Aggregation)
-- Monthly summary of key supply chain KPIs by product category and region.
-- =============================================================================
CREATE OR REPLACE VIEW nike_databricks.cpg_supply_chain.v_monthly_sc_scorecard AS
WITH demand AS (
  SELECT
    dd.year, dd.month, dp.category, ddest.region AS demand_region,
    SUM(fsd.units_demanded)      AS total_units_demanded,
    SUM(fsd.units_fulfilled)     AS total_units_fulfilled,
    SUM(fsd.revenue)             AS total_revenue,
    AVG(fsd.fulfillment_rate_pct) AS avg_fulfillment_rate
  FROM nike_databricks.cpg_supply_chain.fact_sales_demand fsd
  JOIN nike_databricks.cpg_supply_chain.dim_date        dd    ON fsd.date_id        = dd.date_id
  JOIN nike_databricks.cpg_supply_chain.dim_product     dp    ON fsd.product_id     = dp.product_id
  JOIN nike_databricks.cpg_supply_chain.dim_destination ddest ON fsd.destination_id = ddest.destination_id
  GROUP BY 1,2,3,4
),
procurement AS (
  SELECT
    dd.year, dd.month, dp.category, dv.region AS vendor_region,
    SUM(fp.total_cost)                AS total_procurement_cost,
    AVG(fp.lead_time_days)            AS avg_lead_time,
    AVG(fp.delivery_variance_pct)     AS avg_delivery_variance
  FROM nike_databricks.cpg_supply_chain.fact_procurement fp
  JOIN nike_databricks.cpg_supply_chain.dim_date    dd ON fp.date_id    = dd.date_id
  JOIN nike_databricks.cpg_supply_chain.dim_product dp ON fp.product_id = dp.product_id
  JOIN nike_databricks.cpg_supply_chain.dim_vendor  dv ON fp.vendor_id  = dv.vendor_id
  GROUP BY 1,2,3,4
),
manufacturing AS (
  SELECT
    dd.year, dd.month, dp.category,
    AVG(fm.machine_utilization_pct) AS avg_machine_util,
    AVG(fm.defect_rate_pct)         AS avg_defect_rate,
    SUM(fm.downtime_hours)          AS total_downtime_hours
  FROM nike_databricks.cpg_supply_chain.fact_manufacturing fm
  JOIN nike_databricks.cpg_supply_chain.dim_date    dd ON fm.date_id    = dd.date_id
  JOIN nike_databricks.cpg_supply_chain.dim_product dp ON fm.product_id = dp.product_id
  GROUP BY 1,2,3
)
SELECT
  d.year,
  d.month,
  d.category,
  d.total_units_demanded,
  d.total_units_fulfilled,
  ROUND(d.avg_fulfillment_rate, 2)      AS avg_fulfillment_rate_pct,
  ROUND(d.total_revenue, 2)             AS total_revenue,
  p.total_procurement_cost,
  ROUND(p.avg_lead_time, 1)             AS avg_vendor_lead_time_days,
  ROUND(p.avg_delivery_variance, 2)     AS avg_vendor_delivery_variance_pct,
  ROUND(m.avg_machine_util, 2)          AS avg_machine_utilization_pct,
  ROUND(m.avg_defect_rate, 4)           AS avg_defect_rate_pct,
  ROUND(m.total_downtime_hours, 1)      AS total_downtime_hours
FROM demand d
LEFT JOIN procurement  p ON d.year = p.year AND d.month = p.month AND d.category = p.category
LEFT JOIN manufacturing m ON d.year = m.year AND d.month = m.month AND d.category = m.category
ORDER BY d.year, d.month, d.category;
