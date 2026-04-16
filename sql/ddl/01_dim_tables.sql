-- =============================================================================
-- CPG Supply Chain Data Model
-- DDL: Dimension Tables (Databricks Delta Lake)
-- Compatible: Databricks Runtime 12.x+, Delta Lake 2.x+
-- Schema: cpg_supply_chain
-- =============================================================================
-- Notes:
--   * Delta Lake does not enforce UNIQUE or FK constraints at the storage layer.
--     Uniqueness is guaranteed by the data generator and enforced via MERGE
--     operations in ELT pipelines.
--   * COMMENT ON COLUMN provides semantic layer documentation.
--   * Tables are PARTITIONED BY region for common query patterns.
--   * TBLPROPERTIES includes Delta-specific optimisations.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS cpg_supply_chain
  COMMENT 'CPG Supply Chain dimensional model – Kimberly-Clark style ontology';

-- =============================================================================
-- DIM_DATE
-- Calendar date spine used as FK by all fact tables.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_date (
  date_id      STRING    NOT NULL  COMMENT 'Unique identifier for each calendar date record (UUID primary key)',
  full_date    DATE      NOT NULL  COMMENT 'The complete calendar date value (YYYY-MM-DD format)',
  year         INT       NOT NULL  COMMENT 'Calendar year extracted from the full date (e.g., 2024)',
  quarter      INT       NOT NULL  COMMENT 'Fiscal or calendar quarter number (1-4)',
  month        INT       NOT NULL  COMMENT 'Calendar month number (1-12)',
  week         INT       NOT NULL  COMMENT 'ISO week number of the year (1-53)',
  month_name   STRING    NOT NULL  COMMENT 'Full name of the month (e.g., January, February)',
  day_of_week  STRING    NOT NULL  COMMENT 'Name of the day of the week (e.g., Monday, Tuesday)',
  is_weekend   BOOLEAN   NOT NULL  COMMENT 'Flag indicating whether the date falls on a Saturday or Sunday (TRUE/FALSE)',
  is_holiday   BOOLEAN   NOT NULL  COMMENT 'Flag indicating whether the date is a recognized public or company holiday (TRUE/FALSE)'
)
USING DELTA
COMMENT 'Calendar date dimension – one row per calendar day'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'supply_chain',
  'owner'                            = 'data_engineering'
);

-- Constraint: date_id must be unique (enforced via MERGE in ELT)
ALTER TABLE cpg_supply_chain.dim_date
  ADD CONSTRAINT pk_dim_date CHECK (date_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_date
  ADD CONSTRAINT ck_dim_date_quarter CHECK (quarter BETWEEN 1 AND 4);

ALTER TABLE cpg_supply_chain.dim_date
  ADD CONSTRAINT ck_dim_date_month CHECK (month BETWEEN 1 AND 12);

ALTER TABLE cpg_supply_chain.dim_date
  ADD CONSTRAINT ck_dim_date_week CHECK (week BETWEEN 1 AND 53);


-- =============================================================================
-- DIM_VENDOR
-- Raw material suppliers, co-packers, and 3PL providers.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_vendor (
  vendor_id           STRING    NOT NULL  COMMENT 'Unique identifier for each vendor record (UUID primary key)',
  vendor_name         STRING    NOT NULL  COMMENT 'Full legal or trade name of the vendor/supplier',
  vendor_type         STRING    NOT NULL  COMMENT 'Classification of the vendor (e.g., raw material, contract manufacturer, 3PL)',
  country             STRING    NOT NULL  COMMENT 'Country where the vendor is headquartered or primarily operates',
  region              STRING    NOT NULL  COMMENT 'Geographic region of the vendor (e.g., APAC, EMEA, North America)',
  tier                STRING    NOT NULL  COMMENT 'Vendor tier classification indicating strategic importance (e.g., Tier 1, Tier 2, Tier 3)',
  reliability_score   DOUBLE    NOT NULL  COMMENT 'Composite reliability score (0-1 or 0-100) based on past delivery performance and quality metrics',
  avg_lead_time_days  DOUBLE    NOT NULL  COMMENT 'Average number of days from purchase order placement to goods receipt for this vendor',
  active              BOOLEAN   NOT NULL  COMMENT 'Indicates whether the vendor is currently active and eligible for new purchase orders (TRUE/FALSE)'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Vendor/supplier master data for procurement and sourcing analysis'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'supply_chain'
);

ALTER TABLE cpg_supply_chain.dim_vendor
  ADD CONSTRAINT pk_dim_vendor CHECK (vendor_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_vendor
  ADD CONSTRAINT ck_dim_vendor_reliability CHECK (reliability_score BETWEEN 0.0 AND 1.0);

ALTER TABLE cpg_supply_chain.dim_vendor
  ADD CONSTRAINT ck_dim_vendor_lead_time CHECK (avg_lead_time_days > 0);

ALTER TABLE cpg_supply_chain.dim_vendor
  ADD CONSTRAINT ck_dim_vendor_tier CHECK (tier IN ('Tier 1', 'Tier 2', 'Tier 3'));

ALTER TABLE cpg_supply_chain.dim_vendor
  ADD CONSTRAINT ck_dim_vendor_region CHECK (
    region IN ('North America', 'EMEA', 'APAC', 'Latin America')
  );


-- =============================================================================
-- DIM_PLANT
-- Manufacturing and conversion plant master.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_plant (
  plant_id               STRING    NOT NULL  COMMENT 'Unique identifier for each manufacturing or distribution plant (UUID primary key)',
  plant_name             STRING    NOT NULL  COMMENT 'Full descriptive name of the plant facility',
  plant_code             STRING    NOT NULL  COMMENT 'Short alphanumeric code used to reference the plant in systems and reports',
  country                STRING    NOT NULL  COMMENT 'Country where the plant is physically located',
  region                 STRING    NOT NULL  COMMENT 'Geographic region of the plant (e.g., APAC, EMEA, North America)',
  capacity_units_per_day DOUBLE    NOT NULL  COMMENT 'Maximum number of units the plant can produce or process in a single day under normal conditions',
  plant_type             STRING    NOT NULL  COMMENT 'Type or function of the plant (e.g., Assembly, Fabrication, Packaging, Distribution)',
  active                 BOOLEAN   NOT NULL  COMMENT 'Indicates whether the plant is currently operational and accepting production orders (TRUE/FALSE)'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Manufacturing plant master data for production analysis'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'supply_chain'
);

ALTER TABLE cpg_supply_chain.dim_plant
  ADD CONSTRAINT pk_dim_plant CHECK (plant_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_plant
  ADD CONSTRAINT ck_dim_plant_capacity CHECK (capacity_units_per_day > 0);

ALTER TABLE cpg_supply_chain.dim_plant
  ADD CONSTRAINT ck_dim_plant_type CHECK (
    plant_type IN ('Assembly', 'Converting', 'Packaging', 'Nonwoven Mfg', 'Distribution')
  );


-- =============================================================================
-- DIM_SHIFT
-- Work shift definitions for manufacturing operations.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_shift (
  shift_id         STRING     NOT NULL  COMMENT 'Unique identifier for each work shift record (UUID primary key)',
  shift_name       STRING     NOT NULL  COMMENT 'Descriptive name of the shift (e.g., Morning Shift, Night Shift, Mid Shift)',
  shift_start      TIMESTAMP  NOT NULL  COMMENT 'Scheduled start timestamp of the shift (date and time)',
  shift_end        TIMESTAMP  NOT NULL  COMMENT 'Scheduled end timestamp of the shift (date and time)',
  shift_supervisor STRING     NOT NULL  COMMENT 'Name or employee ID of the supervisor responsible for overseeing the shift'
)
USING DELTA
COMMENT 'Work shift master data – typically 3 shifts (Morning, Afternoon, Night)'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'supply_chain'
);

ALTER TABLE cpg_supply_chain.dim_shift
  ADD CONSTRAINT pk_dim_shift CHECK (shift_id IS NOT NULL);


-- =============================================================================
-- DIM_WAREHOUSE
-- Finished goods DCs, raw material stores, and cross-dock facilities.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_warehouse (
  warehouse_id           STRING    NOT NULL  COMMENT 'Unique identifier for each warehouse or storage facility (UUID primary key)',
  warehouse_name         STRING    NOT NULL  COMMENT 'Full descriptive name of the warehouse',
  warehouse_code         STRING    NOT NULL  COMMENT 'Short alphanumeric code used to reference the warehouse in systems and reports',
  type                   STRING    NOT NULL  COMMENT 'Type of warehouse (e.g., Finished Goods, Raw Materials, Cold Storage, Cross-Dock)',
  country                STRING    NOT NULL  COMMENT 'Country where the warehouse is physically located',
  region                 STRING    NOT NULL  COMMENT 'Geographic region of the warehouse (e.g., APAC, EMEA, North America)',
  storage_capacity_units DOUBLE    NOT NULL  COMMENT 'Maximum number of units the warehouse can store at full capacity',
  active                 BOOLEAN   NOT NULL  COMMENT 'Indicates whether the warehouse is currently active and available for inventory operations (TRUE/FALSE)'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Warehouse and DC master data for inventory and shipment analysis'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'supply_chain'
);

ALTER TABLE cpg_supply_chain.dim_warehouse
  ADD CONSTRAINT pk_dim_warehouse CHECK (warehouse_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_warehouse
  ADD CONSTRAINT ck_dim_warehouse_capacity CHECK (storage_capacity_units > 0);

ALTER TABLE cpg_supply_chain.dim_warehouse
  ADD CONSTRAINT ck_dim_warehouse_type CHECK (
    type IN ('Finished Goods DC', 'Raw Materials', 'Cold Storage',
             'Cross-Dock', 'Bonded Warehouse')
  );


-- =============================================================================
-- DIM_CUSTOMER
-- Retail and B2B customer master with channel segmentation.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_customer (
  customer_id      STRING    NOT NULL  COMMENT 'Unique identifier for each customer record (UUID primary key)',
  customer_name    STRING    NOT NULL  COMMENT 'Full name of the customer or business entity',
  customer_segment STRING    NOT NULL  COMMENT 'Market segment the customer belongs to (e.g., Enterprise, SMB, Retail, Wholesale)',
  country          STRING    NOT NULL  COMMENT 'Country where the customer is located or registered',
  region           STRING    NOT NULL  COMMENT 'Geographic region of the customer (e.g., APAC, EMEA, North America)',
  channel          STRING    NOT NULL  COMMENT 'Sales or distribution channel through which the customer orders (e.g., Direct, E-Commerce, Distributor)',
  active           BOOLEAN   NOT NULL  COMMENT 'Indicates whether the customer account is currently active (TRUE/FALSE)'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Customer master data for demand and sales analysis'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'commercial'
);

ALTER TABLE cpg_supply_chain.dim_customer
  ADD CONSTRAINT pk_dim_customer CHECK (customer_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_customer
  ADD CONSTRAINT ck_dim_customer_channel CHECK (
    channel IN ('Direct', 'E-Commerce', 'Distributor', 'Wholesale', 'B2B Direct', 'Drop-Ship')
  );


-- =============================================================================
-- DIM_DESTINATION
-- Delivery destination master: retail stores, customer DCs, 3PLs.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_destination (
  destination_id   STRING    NOT NULL  COMMENT 'Unique identifier for each shipment or delivery destination (UUID primary key)',
  destination_name STRING    NOT NULL  COMMENT 'Full name of the destination location (e.g., store name, customer site, distribution hub)',
  destination_type STRING    NOT NULL  COMMENT 'Type of destination (e.g., Retail Store, Customer DC, 3PL Facility, End Customer)',
  country          STRING    NOT NULL  COMMENT 'Country where the destination is located',
  region           STRING    NOT NULL  COMMENT 'Geographic region of the destination (e.g., APAC, EMEA, North America)',
  lat              DOUBLE              COMMENT 'Latitude coordinate of the destination for geographic/routing analysis',
  lon              DOUBLE              COMMENT 'Longitude coordinate of the destination for geographic/routing analysis'
)
USING DELTA
PARTITIONED BY (region)
COMMENT 'Shipment and demand destination master data'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'supply_chain'
);

ALTER TABLE cpg_supply_chain.dim_destination
  ADD CONSTRAINT pk_dim_destination CHECK (destination_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_destination
  ADD CONSTRAINT ck_dim_destination_lat CHECK (lat IS NULL OR lat BETWEEN -90 AND 90);

ALTER TABLE cpg_supply_chain.dim_destination
  ADD CONSTRAINT ck_dim_destination_lon CHECK (lon IS NULL OR lon BETWEEN -180 AND 180);


-- =============================================================================
-- DIM_CARRIER
-- Logistics carrier master: road, ocean, air, rail providers.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_carrier (
  carrier_id            STRING    NOT NULL  COMMENT 'Unique identifier for each logistics carrier or freight provider (UUID primary key)',
  carrier_name          STRING    NOT NULL  COMMENT 'Full legal or trade name of the carrier',
  carrier_type          STRING    NOT NULL  COMMENT 'Mode or type of carrier (e.g., Air, Ocean, Road, Rail, Courier)',
  country               STRING    NOT NULL  COMMENT 'Country where the carrier is headquartered or primarily operates',
  avg_transit_days      DOUBLE    NOT NULL  COMMENT 'Historical average number of transit days from pickup to delivery for this carrier',
  on_time_delivery_pct  DOUBLE    NOT NULL  COMMENT 'Percentage of shipments delivered on or before the expected delivery date (0-100)',
  active                BOOLEAN   NOT NULL  COMMENT 'Indicates whether the carrier is currently active and available for scheduling (TRUE/FALSE)'
)
USING DELTA
COMMENT 'Logistics carrier master data for shipment performance analysis'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'logistics'
);

ALTER TABLE cpg_supply_chain.dim_carrier
  ADD CONSTRAINT pk_dim_carrier CHECK (carrier_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_carrier
  ADD CONSTRAINT ck_dim_carrier_otd CHECK (on_time_delivery_pct BETWEEN 0 AND 100);

ALTER TABLE cpg_supply_chain.dim_carrier
  ADD CONSTRAINT ck_dim_carrier_transit CHECK (avg_transit_days > 0);

ALTER TABLE cpg_supply_chain.dim_carrier
  ADD CONSTRAINT ck_dim_carrier_type CHECK (
    carrier_type IN ('Air', 'Ocean', 'Road', 'Rail', 'Courier')
  );


-- =============================================================================
-- DIM_PRODUCT
-- Product/SKU master for all CPG items across categories and brands.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cpg_supply_chain.dim_product (
  product_id      STRING    NOT NULL  COMMENT 'Unique identifier for each product/SKU record (UUID primary key)',
  sku             STRING    NOT NULL  COMMENT 'Stock Keeping Unit - unique alphanumeric code used to identify and track the product in inventory',
  product_name    STRING    NOT NULL  COMMENT 'Full descriptive name of the product',
  category        STRING    NOT NULL  COMMENT 'Top-level category: Baby & Child Care | Personal Care | Family Care | Professional | Health & Hygiene',
  sub_category    STRING    NOT NULL  COMMENT 'Product sub-category within a broader category hierarchy (e.g., Electronics > Smartphones)',
  brand           STRING    NOT NULL  COMMENT 'Brand name under which the product is sold or manufactured',
  unit_weight_kg  DOUBLE    NOT NULL  COMMENT 'Physical weight of one unit of the product in kilograms, used for freight and handling calculations',
  packaging_type  STRING    NOT NULL  COMMENT 'Type of packaging used for the product (e.g., Box, Pallet, Crate, Blister Pack)',
  active          BOOLEAN   NOT NULL  COMMENT 'Indicates whether the product is currently active and available for sale or production (TRUE/FALSE)'
)
USING DELTA
PARTITIONED BY (category)
COMMENT 'Product/SKU master data – CPG brand portfolio'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true',
  'quality.layer'                    = 'gold',
  'domain'                           = 'commercial'
);

ALTER TABLE cpg_supply_chain.dim_product
  ADD CONSTRAINT pk_dim_product CHECK (product_id IS NOT NULL);

ALTER TABLE cpg_supply_chain.dim_product
  ADD CONSTRAINT ck_dim_product_weight CHECK (unit_weight_kg > 0);

ALTER TABLE cpg_supply_chain.dim_product
  ADD CONSTRAINT ck_dim_product_category CHECK (
    category IN (
      'Baby & Child Care', 'Personal Care', 'Family Care',
      'Professional', 'Health & Hygiene'
    )
  );
