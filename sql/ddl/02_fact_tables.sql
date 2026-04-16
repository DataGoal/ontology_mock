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
  procurement_id         STRING    NOT NULL  COMMENT 'Unique identifier for each procurement transaction record (UUID primary key)',
  vendor_id              STRING    NOT NULL  COMMENT 'Foreign key linking to dim_vendor - identifies the supplier from whom the goods were ordered',
  product_id             STRING    NOT NULL  COMMENT 'Foreign key linking to dim_product - identifies the product that was procured',
  date_id                STRING    NOT NULL  COMMENT 'Foreign key linking to dim_date - identifies the date the purchase order was placed',
  warehouse_id           STRING    NOT NULL  COMMENT 'Foreign key linking to dim_warehouse - identifies the destination warehouse for the received goods',
  quantity_ordered       DOUBLE    NOT NULL  COMMENT 'Total number of units requested in the purchase order',
  quantity_delivered     DOUBLE    NOT NULL  COMMENT 'Actual number of units received/delivered by the vendor against the purchase order',
  delivery_variance_pct  DOUBLE    NOT NULL  COMMENT 'Percentage difference between quantity ordered and quantity delivered; positive = over-delivered, negative = under-delivered',
  unit_cost              DOUBLE    NOT NULL  COMMENT 'Purchase price per unit of the product as agreed with the vendor (in reporting currency)',
  total_cost             DOUBLE    NOT NULL  COMMENT 'Total procurement cost for the transaction (quantity_delivered x unit_cost)',
  lead_time_days         INT       NOT NULL  COMMENT 'Actual number of calendar days elapsed between order placement and delivery',
  status                 STRING    NOT NULL  COMMENT 'Current status of the procurement order (e.g., Pending, In Transit, Received, Cancelled)'
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
  manufacturing_id         STRING    NOT NULL  COMMENT 'Unique identifier for each manufacturing production run record (UUID primary key)',
  plant_id                 STRING    NOT NULL  COMMENT 'Foreign key linking to dim_plant - identifies the plant where production took place',
  product_id               STRING    NOT NULL  COMMENT 'Foreign key linking to dim_product - identifies the product that was manufactured',
  date_id                  STRING    NOT NULL  COMMENT 'Foreign key linking to dim_date - identifies the date of the production run',
  shift_id                 STRING    NOT NULL  COMMENT 'Foreign key linking to dim_shift - identifies the work shift during which production occurred',
  units_planned            DOUBLE    NOT NULL  COMMENT 'Number of units scheduled for production in this run',
  units_produced           DOUBLE    NOT NULL  COMMENT 'Actual number of units successfully produced during the run',
  defect_rate_pct          DOUBLE    NOT NULL  COMMENT 'Percentage of produced units that failed quality inspection or were deemed defective (0-100)',
  throughput_rate          DOUBLE    NOT NULL  COMMENT 'Rate of units produced per hour or per shift, measuring production efficiency',
  machine_utilization_pct  DOUBLE    NOT NULL  COMMENT 'Percentage of total available machine capacity utilized during the production run (0-100)',
  downtime_hours           DOUBLE    NOT NULL  COMMENT 'Total hours of unplanned or planned machine/equipment downtime recorded during the shift'
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
  inventory_id   STRING    NOT NULL  COMMENT 'Unique identifier for each inventory snapshot record (UUID primary key)',
  warehouse_id   STRING    NOT NULL  COMMENT 'Foreign key linking to dim_warehouse - identifies the warehouse where inventory is held',
  product_id     STRING    NOT NULL  COMMENT 'Foreign key linking to dim_product - identifies the product being tracked',
  date_id        STRING    NOT NULL  COMMENT 'Foreign key linking to dim_date - identifies the date of the inventory snapshot',
  stock_on_hand  DOUBLE    NOT NULL  COMMENT 'Actual quantity of units physically available in the warehouse on the snapshot date',
  reorder_point  DOUBLE    NOT NULL  COMMENT 'Minimum stock level threshold below which a replenishment order should be triggered',
  safety_stock   DOUBLE    NOT NULL  COMMENT 'Buffer stock maintained to protect against demand uncertainty or supply delays',
  stockout_flag  DOUBLE    NOT NULL  COMMENT 'Binary flag indicating that stock on hand has dropped to zero or below the safety stock level (1 = stockout, 0 = no stockout)',
  overstock_flag DOUBLE    NOT NULL  COMMENT 'Binary flag indicating that stock on hand significantly exceeds demand requirements, tying up working capital (1 = overstock, 0 = normal)'
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
  shipment_id              STRING    NOT NULL  COMMENT 'Unique identifier for each shipment record (UUID primary key)',
  carrier_id               STRING    NOT NULL  COMMENT 'Foreign key linking to dim_carrier - identifies the logistics provider handling the shipment',
  product_id               STRING    NOT NULL  COMMENT 'Foreign key linking to dim_product - identifies the product being shipped',
  date_id                  STRING    NOT NULL  COMMENT 'Foreign key linking to dim_date - identifies the date the shipment was dispatched',
  origin_warehouse_id      STRING    NOT NULL  COMMENT 'Foreign key linking to dim_warehouse - identifies the originating warehouse from which the shipment departed',
  destination_id           STRING    NOT NULL  COMMENT 'Foreign key linking to dim_destination - identifies the delivery endpoint for the shipment',
  quantity_shipped         DOUBLE    NOT NULL  COMMENT 'Total number of units loaded and dispatched in this shipment',
  quantity_received        DOUBLE    NOT NULL  COMMENT 'Total number of units confirmed as received at the destination',
  transit_days_actual      DOUBLE    NOT NULL  COMMENT 'Actual number of days elapsed from shipment dispatch to delivery at destination',
  transit_days_expected    DOUBLE    NOT NULL  COMMENT 'Carrier-committed or SLA-based number of transit days promised at time of booking',
  delivery_variance_days   DOUBLE    NOT NULL  COMMENT 'Difference between actual and expected transit days; positive = late, negative = early delivery',
  freight_cost             DOUBLE    NOT NULL  COMMENT 'Total freight and logistics cost charged by the carrier for this shipment (in reporting currency)',
  shipment_status          STRING    NOT NULL  COMMENT 'Current status of the shipment (e.g., In Transit, Delivered, Delayed, Lost, Returned)'
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
  demand_id             STRING    NOT NULL  COMMENT 'Unique identifier for each sales demand record (UUID primary key)',
  product_id            STRING    NOT NULL  COMMENT 'Foreign key linking to dim_product - identifies the product for which demand was recorded',
  customer_id           STRING    NOT NULL  COMMENT 'Foreign key linking to dim_customer - identifies the customer who placed the demand or order',
  date_id               STRING    NOT NULL  COMMENT 'Foreign key linking to dim_date - identifies the date the demand or order was placed',
  destination_id        STRING    NOT NULL  COMMENT 'Foreign key linking to dim_destination - identifies the delivery address or destination for the order',
  units_demanded        DOUBLE    NOT NULL  COMMENT 'Total number of units requested by the customer in the order or demand signal',
  units_fulfilled       DOUBLE    NOT NULL  COMMENT 'Actual number of units shipped and fulfilled against the customer demand',
  fulfillment_rate_pct  DOUBLE    NOT NULL  COMMENT 'Percentage of demand that was successfully fulfilled (units_fulfilled / units_demanded x 100)',
  revenue               DOUBLE    NOT NULL  COMMENT 'Total revenue generated from this demand record (units_fulfilled x selling price per unit, in reporting currency)'
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
