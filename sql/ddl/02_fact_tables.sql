-- =============================================================================
-- CPG Supply Chain Data Model
-- DDL: Fact Tables (Databricks Delta Lake)
-- Compatible: Databricks Runtime 12.x+, Delta Lake 2.x+
-- Schema: cpg_supply_chain
-- =============================================================================
-- Partitioning strategy:
--   All fact tables are partitioned by year/month-derived columns for
--   time-range query pruning, the most common access pattern in supply chain BI.
-- =============================================================================

-- =============================================================================
-- FACT_PROCUREMENT
-- Vendor purchase orders: ordered vs delivered quantities, costs, lead times.
-- Grain: One row per purchase order line item.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.fact_procurement (
  procurement_id         STRING    NOT NULL  COMMENT 'UUID primary key for each procurement transaction',
  vendor_id              STRING    NOT NULL  COMMENT 'FK → dim_vendor.vendor_id',
  product_id             STRING    NOT NULL  COMMENT 'FK → dim_product.product_id',
  date_id                STRING    NOT NULL  COMMENT 'FK → dim_date.date_id (PO placement date)',
  warehouse_id           STRING    NOT NULL  COMMENT 'FK → dim_warehouse.warehouse_id (receiving DC)',
  quantity_ordered       DOUBLE    NOT NULL  COMMENT 'Total units requested in the purchase order',
  quantity_delivered     DOUBLE    NOT NULL  COMMENT 'Actual units received against the PO',
  delivery_variance_pct  DOUBLE    NOT NULL  COMMENT '% difference between delivered and ordered; positive = over-delivery',
  unit_cost              DOUBLE    NOT NULL  COMMENT 'Purchase price per unit (reporting currency)',
  total_cost             DOUBLE    NOT NULL  COMMENT 'Total procurement cost = quantity_delivered × unit_cost',
  lead_time_days         INT       NOT NULL  COMMENT 'Actual calendar days from PO placement to delivery',
  status                 STRING    NOT NULL  COMMENT 'PO status: Received | In Transit | Pending | Partially Received | Cancelled'
)
USING DELTA
PARTITIONED BY (date_id)
COMMENT 'Procurement fact table – purchase order grain, one row per PO line'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'procurement'
);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT pk_fact_procurement CHECK (procurement_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT ck_fp_quantity_ordered CHECK (quantity_ordered >= 0);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT ck_fp_quantity_delivered CHECK (quantity_delivered >= 0);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT ck_fp_unit_cost CHECK (unit_cost >= 0);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT ck_fp_total_cost CHECK (total_cost >= 0);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT ck_fp_lead_time CHECK (lead_time_days >= 0);

ALTER TABLE cpg_supply_chain.fact_procurement
  ADD CONSTRAINT ck_fp_status CHECK (
    status IN ('Received', 'In Transit', 'Pending', 'Partially Received', 'Cancelled')
  );


-- =============================================================================
-- FACT_MANUFACTURING
-- Plant-level production runs: planned vs actual output and quality KPIs.
-- Grain: One row per plant × product × shift × date production run.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.fact_manufacturing (
  manufacturing_id         STRING    NOT NULL  COMMENT 'UUID primary key for each production run record',
  plant_id                 STRING    NOT NULL  COMMENT 'FK → dim_plant.plant_id',
  product_id               STRING    NOT NULL  COMMENT 'FK → dim_product.product_id',
  date_id                  STRING    NOT NULL  COMMENT 'FK → dim_date.date_id (production date)',
  shift_id                 STRING    NOT NULL  COMMENT 'FK → dim_shift.shift_id',
  units_planned            DOUBLE    NOT NULL  COMMENT 'Units scheduled for production in this run',
  units_produced           DOUBLE    NOT NULL  COMMENT 'Actual units successfully produced',
  defect_rate_pct          DOUBLE    NOT NULL  COMMENT '% of produced units failing quality inspection (0–100)',
  throughput_rate          DOUBLE    NOT NULL  COMMENT 'Units produced per hour (productivity metric)',
  machine_utilization_pct  DOUBLE    NOT NULL  COMMENT '% of total available machine capacity utilised (0–100)',
  downtime_hours           DOUBLE    NOT NULL  COMMENT 'Total unplanned or planned equipment downtime in hours'
)
USING DELTA
PARTITIONED BY (date_id)
COMMENT 'Manufacturing fact table – production run grain, quality and efficiency KPIs'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'manufacturing'
);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT pk_fact_manufacturing CHECK (manufacturing_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT ck_fm_units_planned CHECK (units_planned >= 0);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT ck_fm_units_produced CHECK (units_produced >= 0);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT ck_fm_defect_rate CHECK (defect_rate_pct BETWEEN 0 AND 100);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT ck_fm_machine_util CHECK (machine_utilization_pct BETWEEN 0 AND 100);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT ck_fm_downtime CHECK (downtime_hours >= 0);

ALTER TABLE cpg_supply_chain.fact_manufacturing
  ADD CONSTRAINT ck_fm_throughput CHECK (throughput_rate >= 0);


-- =============================================================================
-- FACT_INVENTORY
-- Daily warehouse inventory snapshots with stock health flags.
-- Grain: One row per warehouse × product × date snapshot.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.fact_inventory (
  inventory_id   STRING    NOT NULL  COMMENT 'UUID primary key for each inventory snapshot',
  warehouse_id   STRING    NOT NULL  COMMENT 'FK → dim_warehouse.warehouse_id',
  product_id     STRING    NOT NULL  COMMENT 'FK → dim_product.product_id',
  date_id        STRING    NOT NULL  COMMENT 'FK → dim_date.date_id (snapshot date)',
  stock_on_hand  DOUBLE    NOT NULL  COMMENT 'Physical units available in warehouse on snapshot date',
  reorder_point  DOUBLE    NOT NULL  COMMENT 'Minimum threshold below which replenishment should trigger',
  safety_stock   DOUBLE    NOT NULL  COMMENT 'Buffer stock to absorb demand uncertainty and supply delays',
  stockout_flag  DOUBLE    NOT NULL  COMMENT '1 = stock_on_hand ≤ safety_stock (stockout or near-miss), 0 = normal',
  overstock_flag DOUBLE    NOT NULL  COMMENT '1 = stock_on_hand ≥ 3× reorder_point (excess inventory), 0 = normal'
)
USING DELTA
PARTITIONED BY (date_id)
COMMENT 'Inventory snapshot fact table – daily position by warehouse and SKU'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'inventory'
);

ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT pk_fact_inventory CHECK (inventory_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT ck_fi_stock_on_hand CHECK (stock_on_hand >= 0);

ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT ck_fi_reorder_point CHECK (reorder_point >= 0);

ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT ck_fi_safety_stock CHECK (safety_stock >= 0);

ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT ck_fi_stockout_flag CHECK (stockout_flag IN (0, 1));

ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT ck_fi_overstock_flag CHECK (overstock_flag IN (0, 1));

-- Business rule: stockout and overstock cannot both be 1
ALTER TABLE cpg_supply_chain.fact_inventory
  ADD CONSTRAINT ck_fi_flag_mutex CHECK (
    NOT (stockout_flag = 1 AND overstock_flag = 1)
  );


-- =============================================================================
-- FACT_SHIPMENT
-- Outbound shipment records: transit performance, quantities, freight cost.
-- Grain: One row per shipment (carrier × origin × destination × product × date).
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.fact_shipment (
  shipment_id              STRING    NOT NULL  COMMENT 'UUID primary key for each shipment record',
  carrier_id               STRING    NOT NULL  COMMENT 'FK → dim_carrier.carrier_id',
  product_id               STRING    NOT NULL  COMMENT 'FK → dim_product.product_id',
  date_id                  STRING    NOT NULL  COMMENT 'FK → dim_date.date_id (dispatch date)',
  origin_warehouse_id      STRING    NOT NULL  COMMENT 'FK → dim_warehouse.warehouse_id (originating DC)',
  destination_id           STRING    NOT NULL  COMMENT 'FK → dim_destination.destination_id',
  quantity_shipped         DOUBLE    NOT NULL  COMMENT 'Total units loaded and dispatched',
  quantity_received        DOUBLE    NOT NULL  COMMENT 'Total units confirmed received at destination',
  transit_days_actual      DOUBLE    NOT NULL  COMMENT 'Actual days from dispatch to delivery',
  transit_days_expected    DOUBLE    NOT NULL  COMMENT 'Carrier-committed or SLA transit days',
  delivery_variance_days   DOUBLE    NOT NULL  COMMENT 'Actual − Expected; positive = late, negative = early',
  freight_cost             DOUBLE    NOT NULL  COMMENT 'Total freight cost charged by carrier (reporting currency)',
  shipment_status          STRING    NOT NULL  COMMENT 'Status: Delivered | In Transit | Delayed | Returned | Lost | Cancelled'
)
USING DELTA
PARTITIONED BY (date_id)
COMMENT 'Shipment fact table – outbound logistics grain with transit KPIs'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'logistics'
);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT pk_fact_shipment CHECK (shipment_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT ck_fs_qty_shipped CHECK (quantity_shipped >= 0);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT ck_fs_qty_received CHECK (quantity_received >= 0);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT ck_fs_transit_actual CHECK (transit_days_actual >= 0);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT ck_fs_transit_expected CHECK (transit_days_expected >= 0);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT ck_fs_freight_cost CHECK (freight_cost >= 0);

ALTER TABLE cpg_supply_chain.fact_shipment
  ADD CONSTRAINT ck_fs_status CHECK (
    shipment_status IN ('Delivered', 'In Transit', 'Delayed',
                        'Returned', 'Lost', 'Cancelled')
  );


-- =============================================================================
-- FACT_SALES_DEMAND
-- Customer demand and order fulfillment with revenue.
-- Grain: One row per customer × product × destination × date demand signal.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.fact_sales_demand (
  demand_id             STRING    NOT NULL  COMMENT 'UUID primary key for each demand record',
  product_id            STRING    NOT NULL  COMMENT 'FK → dim_product.product_id',
  customer_id           STRING    NOT NULL  COMMENT 'FK → dim_customer.customer_id',
  date_id               STRING    NOT NULL  COMMENT 'FK → dim_date.date_id (order placement date)',
  destination_id        STRING    NOT NULL  COMMENT 'FK → dim_destination.destination_id',
  units_demanded        DOUBLE    NOT NULL  COMMENT 'Total units requested by customer',
  units_fulfilled       DOUBLE    NOT NULL  COMMENT 'Actual units shipped and fulfilled',
  fulfillment_rate_pct  DOUBLE    NOT NULL  COMMENT 'units_fulfilled / units_demanded × 100 (OTIF proxy)',
  revenue               DOUBLE    NOT NULL  COMMENT 'Total revenue from this demand record (reporting currency)'
)
USING DELTA
PARTITIONED BY (date_id)
COMMENT 'Sales demand fact table – customer order grain with fulfillment and revenue KPIs'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'commercial'
);

ALTER TABLE cpg_supply_chain.fact_sales_demand
  ADD CONSTRAINT pk_fact_sales_demand CHECK (demand_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.fact_sales_demand
  ADD CONSTRAINT ck_fsd_units_demanded CHECK (units_demanded >= 0);

ALTER TABLE cpg_supply_chain.fact_sales_demand
  ADD CONSTRAINT ck_fsd_units_fulfilled CHECK (units_fulfilled >= 0);

ALTER TABLE cpg_supply_chain.fact_sales_demand
  ADD CONSTRAINT ck_fsd_fulfillment_rate CHECK (fulfillment_rate_pct BETWEEN 0 AND 100);

ALTER TABLE cpg_supply_chain.fact_sales_demand
  ADD CONSTRAINT ck_fsd_revenue CHECK (revenue >= 0);
