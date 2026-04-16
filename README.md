# CPG Supply Chain Data Generator

> **Domain:** Consumer Packaged Goods (modelled after Kimberly-Clark / P&G style supply chains)
> **Purpose:** Generate realistic, relationship-consistent mock data for a dimensional supply chain data model

---

## Project Overview

This project generates production-quality mock data for a CPG supply chain dimensional model (star schema). It covers the full supply chain lifecycle — from vendor procurement through manufacturing, inventory, logistics, and customer demand — using statistically grounded distributions and realistic CPG reference data (brands, products, vendors, plants, warehouses, carriers).

The generated data is suitable for:
- BI/analytics development and testing
- Data engineering pipeline validation
- Semantic layer / ontology development
- ML model training and prototyping
- Data quality tooling evaluation

---

## Project Structure

```
cpg_data_generator/
│
├── configs/                          # YAML configuration files
│   ├── schema.yaml                   # Table schemas with column types and constraints
│   ├── data_volumes.yaml             # Row counts by profile (dev/staging/prod)
│   ├── distributions.yaml            # Statistical distributions per field
│   └── relationships.yaml            # FK strategies, business rules, generation order
│
├── src/                              # Core generation logic
│   ├── generators/
│   │   ├── base_generator.py         # Abstract base class + shared sampling utilities
│   │   ├── dim_generators.py         # 9 dimension table generators
│   │   └── fact_generators.py        # 5 fact table generators
│   ├── pipeline.py                   # Orchestration: generate → validate → write
│   └── writer.py                     # CSV / Parquet / JSON output
│
├── utils/                            # Shared helpers
│   ├── cpg_reference_data.py         # CPG brand/product/vendor/plant master lists
│   ├── validators.py                 # Schema, RI, and business rule validators
│   └── logger.py                     # Structured logging
│
├── sql/
│   ├── ddl/
│   │   ├── 01_dim_tables.sql         # Databricks Delta DDL for all dimension tables
│   │   ├── 02_fact_tables.sql        # Databricks Delta DDL for all fact tables
│   │   └── 03_views_and_semantic_layer.sql  # Enriched views + supply chain scorecard
│   └── queries/
│       └── sample_analytics.sql      # 8 sample analytics queries (vendor, OTIF, OEE…)
│
├── output/                           # Generated data files (git-ignored)
├── tests/                            # Unit tests
├── main.py                           # CLI entry point
├── requirements.txt
└── README.md
```

---

## Data Model

### Dimension Tables (9)

| Table | Description | Key Columns |
|---|---|---|
| `dim_date` | Calendar date spine | full_date, year, quarter, month, is_holiday |
| `dim_vendor` | Supplier master | vendor_name, tier, reliability_score, avg_lead_time_days |
| `dim_plant` | Manufacturing plants | plant_code, plant_type, capacity_units_per_day |
| `dim_shift` | Work shifts | shift_name, shift_start, shift_end |
| `dim_warehouse` | Distribution centres | warehouse_code, type, storage_capacity_units |
| `dim_carrier` | Logistics carriers | carrier_type, avg_transit_days, on_time_delivery_pct |
| `dim_product` | SKU master | sku, category, sub_category, brand |
| `dim_customer` | Customer accounts | customer_segment, channel |
| `dim_destination` | Delivery destinations | destination_type, lat, lon |

### Fact Tables (5)

| Table | Grain | Key Metrics |
|---|---|---|
| `fact_procurement` | PO line | quantity_ordered, quantity_delivered, total_cost, lead_time_days |
| `fact_manufacturing` | Production run × shift | units_planned/produced, defect_rate_pct, machine_utilization_pct |
| `fact_inventory` | Warehouse × SKU × date | stock_on_hand, reorder_point, safety_stock, stockout/overstock flags |
| `fact_shipment` | Shipment × product | transit_days, delivery_variance_days, freight_cost, OTIF |
| `fact_sales_demand` | Customer order | units_demanded/fulfilled, fulfillment_rate_pct, revenue |

---

## Quick Start

### 1. Install dependencies

```bash
cd cpg_data_generator
pip install -r requirements.txt
```

### 2. Generate dev dataset (default)

```bash
python main.py
```

Generated CSV files will appear in `./output/`.

### 3. Use CLI options

```bash
# Staging profile with parquet output
python main.py --profile staging --format parquet

# Production scale, compressed parquet, skip validation (faster)
python main.py --profile prod --format parquet --compress --no-validate

# Generate only (no file I/O)
python main.py --no-write

# Custom output directory
python main.py --output /data/cpg_mock --format csv
```

### 4. Use as a Python library

```python
from src.pipeline import CPGDataPipeline

pipeline = CPGDataPipeline(configs_dir="configs", output_dir="output")
results  = pipeline.run(write=True, validate=True)

# Access individual DataFrames
dim_product_df      = results["dim_product"]
fact_sales_df       = results["fact_sales_demand"]
fact_inventory_df   = results["fact_inventory"]
```

---

## Configuration Reference

### Profiles (`configs/data_volumes.yaml`)

| Profile | Date Range | Total Rows (approx.) | Use Case |
|---|---|---|---|
| `dev` | 1 year | ~4,300 | Local development, unit tests |
| `staging` | 2 years | ~47,000 | Integration testing, QA |
| `prod` | 5 years | ~1,400,000 | Full-scale analytics, ML training |

### Switching profiles

Edit `active_profile` in `configs/data_volumes.yaml`:
```yaml
active_profile: staging  # dev | staging | prod
```

Or override via CLI: `python main.py --profile prod`

### Adding a new dimension

1. Add the table definition to `configs/schema.yaml`
2. Add a row count entry to `configs/data_volumes.yaml` under each profile
3. Add FK strategies to `configs/relationships.yaml`
4. Add a generator class to `src/generators/dim_generators.py`
5. Register it in `src/pipeline.py → GENERATOR_REGISTRY`
6. Add DDL to `sql/ddl/01_dim_tables.sql`

---

## CPG Domain Reference Data

The generator uses realistic CPG reference data modelled on Kimberly-Clark's portfolio:

**Brands:** Huggies, Pull-Ups, GoodNites, Kleenex, Cottonelle, Scott, Viva, Depend, Poise, U by Kotex, WypAll, Scott Pro, Kleenex Pro

**Product Categories:**
- Baby & Child Care (Diapers, Training Pants, Baby Wipes)
- Personal Care (Feminine Care, Adult Incontinence)
- Family Care (Facial Tissue, Toilet Paper, Paper Towels)
- Professional (Industrial Wipes, Facility Tissue)
- Health & Hygiene (Disinfecting Wipes)

**Vendor Types:** Raw Material, Packaging, Chemical Supplier, Contract Manufacturer, 3PL

**Carrier Types:** Road (FedEx, UPS, J.B. Hunt), Ocean (Maersk, MSC, CMA CGM), Air (DHL, FedEx Express), Rail (DB Schenker)

---

## SQL DDL (Databricks)

The `sql/ddl/` directory contains production-ready Databricks Delta Lake DDL:

```sql
-- Run in order:
-- 1. Create schema and all dimension tables
%run sql/ddl/01_dim_tables.sql

-- 2. Create all fact tables
%run sql/ddl/02_fact_tables.sql

-- 3. Create semantic views and run optimizations
%run sql/ddl/03_views_and_semantic_layer.sql
```

### Semantic Views Available

| View | Description |
|---|---|
| `v_procurement_enriched` | Procurement + vendor + product + warehouse |
| `v_manufacturing_enriched` | Production + plant + product + shift + OEE metrics |
| `v_inventory_health` | Inventory + warehouse + product with health classification |
| `v_shipment_performance` | Shipments + carrier + OTIF flag + cost per unit |
| `v_sales_demand_enriched` | Demand + customer + product + fulfillment band |
| `v_monthly_sc_scorecard` | Cross-domain monthly KPI summary for executive reporting |

---

## Validation

The pipeline runs three validation tiers after generation:

1. **Schema validation** – null checks, type checks, range checks, uniqueness
2. **Business rule validation** – domain logic (e.g. total_cost = qty × unit_cost, flags are mutually exclusive)
3. **Referential integrity** – every FK in every fact table resolves to a valid dimension PK

---

## Design Principles

| Principle | Implementation |
|---|---|
| **Config-driven** | All volumes, distributions, and FK strategies in YAML |
| **Reproducible** | Seeded `numpy.random.default_rng` passed through entire pipeline |
| **Dependency-aware** | Generation order enforced; facts cannot precede their dimensions |
| **Domain-accurate** | CPG-specific distributions (pareto SKU concentration, seasonal demand, lead time variance) |
| **Scalable** | Profiles scale from ~4K rows (dev) to ~1.4M rows (prod) without code changes |
| **Extensible** | Add new tables by implementing `BaseGenerator` and registering in pipeline |
