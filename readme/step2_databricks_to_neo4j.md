# Step 2: Databricks → Neo4j ETL Pipeline
## CPG Supply Chain Knowledge Graph — PoC Static Load Guide

> **PoC Scope:** Static tables only. No incremental loads. No MERGE.
> We use `CREATE` for a clean one-time full load.
> Run this AFTER Step 1 (constraints + sample data cleanup) is complete.

---

## Before You Start — Checklist

```
✅ Step 1 complete — constraints and indexes exist in Neo4j
✅ Sample test nodes from Step 1 are deleted (run cleanup below)
✅ Neo4j Desktop local instance is RUNNING (green status in Desktop app)
✅ You know your Neo4j bolt URL, username, password
✅ Databricks cluster is running
```

### Find your Neo4j connection details

In **Neo4j Desktop**:
1. Click your local DBMS
2. Click the **three-dot menu** → **Manage**
3. You will see: `bolt://localhost:7687`
4. Default username: `neo4j`
5. Password: whatever you set when creating the DBMS

> **Important for PoC:** Your Databricks cluster and Neo4j Desktop are on the
> same laptop. Databricks Community Edition or a local Databricks runtime
> can reach `localhost:7687` directly. If you are on Databricks hosted
> (cloud), see the "Network" note in Section 1 below.

---

## Section 0 — Clean Up Step 1 Sample Data

Before loading real data, wipe the sample nodes you created in Step 1.
Run this in **Neo4j Browser**:

```cypher
// Delete all sample data — keeps constraints and indexes intact
MATCH (n) DETACH DELETE n;

// Verify clean
MATCH (n) RETURN count(n) AS remaining;
// Must return 0 before proceeding
```

---

## Section 1 — Install the Neo4j Python Driver in Databricks

Open a **new Databricks notebook**. In the first cell:

```python
# Cell 1 — Install Neo4j driver
# Run this once per cluster session (or add to cluster init script)
%pip install neo4j
```

After install, restart the Python kernel if prompted:
```python
# Cell 2
dbutils.library.restartPython()
```

> **Network Note (Databricks hosted on cloud):**
> If your Databricks is on Azure/AWS and Neo4j is on your laptop,
> `localhost:7687` will NOT be reachable from the cloud.
> Options for PoC:
> - Use **Databricks Community Edition** (runs locally enough for PoC)
> - OR run the notebook locally using **Databricks Connect**
> - OR temporarily expose Neo4j via **ngrok** (`ngrok tcp 7687`)
>   and use the ngrok URL instead of localhost

---

## Section 2 — Establish and Test the Connection

```python
# Cell 3 — Create free instance from https://neo4j.com/cloud/aura/ 
NEO4J_URI      = "bolt://localhost:7687"  
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "your_password_here"      # your Neo4j password
NEO4J_DATABASE = "neo4j"                   # default database name

from neo4j import GraphDatabase

# Test connection
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

with driver.session(database=NEO4J_DATABASE) as session:
    result = session.run("RETURN 'Connection successful!' AS msg")
    print(result.single()["msg"])

# Expected output: Connection successful!
```

---

## Section 3 — Helper Function

This is the only utility function you need for the entire PoC.
It takes a Cypher query + a list of parameter dicts and runs them in batches.

```python
# Cell 4 — Batch loader utility
def load_to_neo4j(cypher_query, rows, batch_size=500, label="nodes"):
    """
    Runs a Cypher query for each row dict in `rows`, in batches.
    
    cypher_query : string with $param placeholders
    rows         : list of dicts — one dict per node or relationship
    batch_size   : how many rows per Neo4j transaction (500 is safe for PoC)
    label        : display name for progress printing
    """
    total = len(rows)
    loaded = 0

    with driver.session(database=NEO4J_DATABASE) as session:
        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            session.run(cypher_query, {"rows": batch})
            loaded += len(batch)
            print(f"  [{label}] Loaded {loaded}/{total}")

    print(f"  ✅ Done: {total} {label} loaded.\n")
```

> **How it works:** The Cypher query uses `UNWIND $rows AS row` to process
> the entire batch in one round-trip to Neo4j instead of one query per row.
> This is the standard pattern for bulk loading.

---

## Section 4 — Load Dimension Nodes

We load dimensions first because fact relationships reference them.
Order matters: **load all nodes before creating any relationships.**

---

### 4.1 — DIM_VENDOR → Vendor nodes

```python
# Cell 5 — Load Vendor nodes
df_vendor = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_vendor")
                                   # ^^^ replace with your actual table path
vendor_rows = df_vendor.toPandas().to_dict("records")

cypher_vendor = """
UNWIND $rows AS row
CREATE (v:Vendor {
    vendor_id:          row.vendor_id,
    vendor_name:        row.vendor_name,
    vendor_type:        row.vendor_type,
    country:            row.country,
    region:             row.region,
    tier:               row.tier,
    reliability_score:  toFloat(row.reliability_score),
    avg_lead_time_days: toFloat(row.avg_lead_time_days),
    active:             toBoolean(row.active)
})
"""
load_to_neo4j(cypher_vendor, vendor_rows, label="Vendor")
```

---

### 4.2 — DIM_PRODUCT → Product nodes

```python
# Cell 6 — Load Product nodes
df_product = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_product")
product_rows = df_product.toPandas().to_dict("records")

cypher_product = """
UNWIND $rows AS row
CREATE (p:Product {
    product_id:      row.product_id,
    sku:             row.sku,
    product_name:    row.product_name,
    category:        row.category,
    sub_category:    row.sub_category,
    brand:           row.brand,
    unit_weight_kg:  toFloat(row.unit_weight_kg),
    packaging_type:  row.packaging_type,
    active:          toBoolean(row.active)
})
"""
load_to_neo4j(cypher_product, product_rows, label="Product")
```

---

### 4.3 — DIM_PLANT → Plant nodes

```python
# Cell 7 — Load Plant nodes
df_plant = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_plant")
plant_rows = df_plant.toPandas().to_dict("records")

cypher_plant = """
UNWIND $rows AS row
CREATE (pl:Plant {
    plant_id:               row.plant_id,
    plant_name:             row.plant_name,
    plant_code:             row.plant_code,
    country:                row.country,
    region:                 row.region,
    capacity_units_per_day: toFloat(row.capacity_units_per_day),
    plant_type:             row.plant_type,
    active:                 toBoolean(row.active)
})
"""
load_to_neo4j(cypher_plant, plant_rows, label="Plant")
```

---

### 4.4 — DIM_WAREHOUSE → Warehouse nodes

```python
# Cell 8 — Load Warehouse nodes
df_warehouse = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_warehouse")
warehouse_rows = df_warehouse.toPandas().to_dict("records")

cypher_warehouse = """
UNWIND $rows AS row
CREATE (w:Warehouse {
    warehouse_id:           row.warehouse_id,
    warehouse_name:         row.warehouse_name,
    warehouse_code:         row.warehouse_code,
    type:                   row.type,
    country:                row.country,
    region:                 row.region,
    storage_capacity_units: toFloat(row.storage_capacity_units),
    active:                 toBoolean(row.active)
})
"""
load_to_neo4j(cypher_warehouse, warehouse_rows, label="Warehouse")
```

---

### 4.5 — DIM_CUSTOMER → Customer nodes

```python
# Cell 9 — Load Customer nodes
df_customer = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_customer")
customer_rows = df_customer.toPandas().to_dict("records")

cypher_customer = """
UNWIND $rows AS row
CREATE (c:Customer {
    customer_id:       row.customer_id,
    customer_name:     row.customer_name,
    customer_segment:  row.customer_segment,
    country:           row.country,
    region:            row.region,
    channel:           row.channel,
    active:            toBoolean(row.active)
})
"""
load_to_neo4j(cypher_customer, customer_rows, label="Customer")
```

---

### 4.6 — DIM_CARRIER → Carrier nodes

```python
# Cell 10 — Load Carrier nodes
df_carrier = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_carrier")
carrier_rows = df_carrier.toPandas().to_dict("records")

cypher_carrier = """
UNWIND $rows AS row
CREATE (ca:Carrier {
    carrier_id:              row.carrier_id,
    carrier_name:            row.carrier_name,
    carrier_type:            row.carrier_type,
    country:                 row.country,
    avg_transit_days:        toFloat(row.avg_transit_days),
    on_time_delivery_pct:    toFloat(row.on_time_delivery_pct),
    active:                  toBoolean(row.active)
})
"""
load_to_neo4j(cypher_carrier, carrier_rows, label="Carrier")
```

---

### 4.7 — DIM_DESTINATION → Destination nodes

```python
# Cell 11 — Load Destination nodes
df_destination = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_destination")
destination_rows = df_destination.toPandas().to_dict("records")

cypher_destination = """
UNWIND $rows AS row
CREATE (d:Destination {
    destination_id:    row.destination_id,
    destination_name:  row.destination_name,
    destination_type:  row.destination_type,
    country:           row.country,
    region:            row.region,
    lat:               toFloat(row.lat),
    lon:               toFloat(row.lon)
})
"""
load_to_neo4j(cypher_destination, destination_rows, label="Destination")
```

---

### 4.8 — DIM_SHIFT → Shift nodes

```python
# Cell 12 — Load Shift nodes
df_shift = spark.sql("SELECT * FROM nike_databricks.cpg_supply_chain.dim_shift")
shift_rows = df_shift.toPandas().to_dict("records")

cypher_shift = """
UNWIND $rows AS row
CREATE (s:Shift {
    shift_id:          row.shift_id,
    shift_name:        row.shift_name,
    shift_start:       row.shift_start,
    shift_end:         row.shift_end,
    shift_supervisor:  row.shift_supervisor
})
"""
load_to_neo4j(cypher_shift, shift_rows, label="Shift")
```

---

### 4.9 — Verify Node Counts in Neo4j Browser

After all dimension loads, run this in **Neo4j Browser** to confirm:

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC;
```

Expected: row counts matching your Databricks dimension tables exactly.

---

## Section 5 — Load Relationships from Fact Tables

This is where the graph becomes intelligent. Each fact table becomes
**aggregated relationship properties** between dimension nodes.

The pattern for every relationship load is:
1. Read the fact table from Databricks
2. Aggregate metrics per dimension key combination
3. Load as relationship properties using `MATCH + CREATE`

---

### 5.1 — SUPPLIES: Vendor → Product
**Source:** `fact_procurement` aggregated by `vendor_id + product_id`

```python
# Cell 13 — SUPPLIES relationship

df_supplies = spark.sql("""
    SELECT
        vendor_id,
        product_id,
        ROUND(AVG(unit_cost), 4)                    AS avg_unit_cost,
        ROUND(AVG(lead_time_days), 2)               AS avg_lead_time_days,
        ROUND(AVG(delivery_variance_pct), 2)        AS avg_delivery_variance_pct,
        ROUND(AVG(quantity_ordered), 2)             AS avg_quantity_ordered,
        ROUND(AVG(quantity_delivered), 2)           AS avg_quantity_delivered,
        COUNT(*)                                    AS total_orders,
        ROUND(SUM(total_cost), 2)                   AS total_spend,
        MAX(status)                                 AS last_status,
        CASE WHEN AVG(delivery_variance_pct) < -10
             THEN true ELSE false END               AS under_delivery_flag
    FROM nike_databricks.cpg_supply_chain.fact_procurement
    GROUP BY vendor_id, product_id
""")

supplies_rows = df_supplies.toPandas().to_dict("records")

cypher_supplies = """
UNWIND $rows AS row
MATCH (v:Vendor   {vendor_id:  row.vendor_id})
MATCH (p:Product  {product_id: row.product_id})
CREATE (v)-[:SUPPLIES {
    avg_unit_cost:              toFloat(row.avg_unit_cost),
    avg_lead_time_days:         toFloat(row.avg_lead_time_days),
    avg_delivery_variance_pct:  toFloat(row.avg_delivery_variance_pct),
    avg_quantity_ordered:       toFloat(row.avg_quantity_ordered),
    avg_quantity_delivered:     toFloat(row.avg_quantity_delivered),
    total_orders:               toInteger(row.total_orders),
    total_spend:                toFloat(row.total_spend),
    last_status:                row.last_status,
    under_delivery_flag:        toBoolean(row.under_delivery_flag)
}]->(p)
"""
load_to_neo4j(cypher_supplies, supplies_rows, label="SUPPLIES relationships")
```

---

### 5.2 — PRODUCES: Plant → Product
**Source:** `fact_manufacturing` aggregated by `plant_id + product_id`

```python
# Cell 14 — PRODUCES relationship

df_produces = spark.sql("""
    SELECT
        plant_id,
        product_id,
        ROUND(AVG(units_planned), 2)                AS avg_units_planned,
        ROUND(AVG(units_produced), 2)               AS avg_units_produced,
        ROUND(AVG(defect_rate_pct), 4)              AS avg_defect_rate_pct,
        ROUND(AVG(throughput_rate), 2)              AS avg_throughput_rate,
        ROUND(AVG(machine_utilization_pct), 2)      AS avg_machine_utilization_pct,
        ROUND(AVG(downtime_hours), 2)               AS avg_downtime_hours,
        COUNT(*)                                    AS total_production_runs,
        ROUND(SUM(units_produced), 2)               AS total_units_produced,
        ROUND(
            AVG(units_produced) / NULLIF(AVG(units_planned), 0) * 100,
        2)                                          AS avg_attainment_pct
    FROM nike_databricks.cpg_supply_chain.fact_manufacturing
    GROUP BY plant_id, product_id
""")

produces_rows = df_produces.toPandas().to_dict("records")

cypher_produces = """
UNWIND $rows AS row
MATCH (pl:Plant   {plant_id:   row.plant_id})
MATCH (p:Product  {product_id: row.product_id})
CREATE (pl)-[:PRODUCES {
    avg_units_planned:           toFloat(row.avg_units_planned),
    avg_units_produced:          toFloat(row.avg_units_produced),
    avg_defect_rate_pct:         toFloat(row.avg_defect_rate_pct),
    avg_throughput_rate:         toFloat(row.avg_throughput_rate),
    avg_machine_utilization_pct: toFloat(row.avg_machine_utilization_pct),
    avg_downtime_hours:          toFloat(row.avg_downtime_hours),
    total_production_runs:       toInteger(row.total_production_runs),
    total_units_produced:        toFloat(row.total_units_produced),
    avg_attainment_pct:          toFloat(row.avg_attainment_pct)
}]->(p)
"""
load_to_neo4j(cypher_produces, produces_rows, label="PRODUCES relationships")
```

---

### 5.3 — STOCKS: Warehouse → Product
**Source:** `fact_inventory` — latest snapshot per warehouse + product

```python
# Cell 15 — STOCKS relationship

df_stocks = spark.sql("""
    WITH latest AS (
        SELECT
            fi.*,
            ROW_NUMBER() OVER (
                PARTITION BY fi.warehouse_id, fi.product_id
                ORDER BY dd.full_date DESC
            ) AS rn
        FROM nike_databricks.cpg_supply_chain.fact_inventory fi
        JOIN nike_databricks.cpg_supply_chain.dim_date dd
          ON fi.date_id = dd.date_id
    )
    SELECT
        warehouse_id,
        product_id,
        stock_on_hand,
        reorder_point,
        safety_stock,
        stockout_flag,
        overstock_flag
    FROM latest
    WHERE rn = 1
""")

stocks_rows = df_stocks.toPandas().to_dict("records")

cypher_stocks = """
UNWIND $rows AS row
MATCH (w:Warehouse {warehouse_id: row.warehouse_id})
MATCH (p:Product   {product_id:   row.product_id})
CREATE (w)-[:STOCKS {
    stock_on_hand:   toFloat(row.stock_on_hand),
    reorder_point:   toFloat(row.reorder_point),
    safety_stock:    toFloat(row.safety_stock),
    stockout_flag:   toFloat(row.stockout_flag),
    overstock_flag:  toFloat(row.overstock_flag)
}]->(p)
"""
load_to_neo4j(cypher_stocks, stocks_rows, label="STOCKS relationships")
```

---

### 5.4 — SHIPS_TO: Warehouse → Destination
**Source:** `fact_shipment` aggregated by `origin_warehouse_id + destination_id`

```python
# Cell 16 — SHIPS_TO relationship

df_ships = spark.sql("""
    SELECT
        origin_warehouse_id                         AS warehouse_id,
        destination_id,
        ROUND(AVG(transit_days_actual), 2)          AS avg_transit_days_actual,
        ROUND(AVG(transit_days_expected), 2)        AS avg_transit_days_expected,
        ROUND(AVG(delivery_variance_days), 2)       AS avg_delivery_variance_days,
        ROUND(AVG(freight_cost), 2)                 AS avg_freight_cost,
        ROUND(SUM(freight_cost), 2)                 AS total_freight_cost,
        COUNT(*)                                    AS total_shipments,
        ROUND(SUM(quantity_shipped), 2)             AS total_qty_shipped,
        ROUND(SUM(quantity_received), 2)            AS total_qty_received,
        ROUND(
            SUM(CASE WHEN delivery_variance_days <= 0 THEN 1 ELSE 0 END)
            / COUNT(*) * 100,
        2)                                          AS on_time_pct
    FROM nike_databricks.cpg_supply_chain.fact_shipment
    GROUP BY origin_warehouse_id, destination_id
""")

ships_rows = df_ships.toPandas().to_dict("records")

cypher_ships = """
UNWIND $rows AS row
MATCH (w:Warehouse   {warehouse_id:   row.warehouse_id})
MATCH (d:Destination {destination_id: row.destination_id})
CREATE (w)-[:SHIPS_TO {
    avg_transit_days_actual:    toFloat(row.avg_transit_days_actual),
    avg_transit_days_expected:  toFloat(row.avg_transit_days_expected),
    avg_delivery_variance_days: toFloat(row.avg_delivery_variance_days),
    avg_freight_cost:           toFloat(row.avg_freight_cost),
    total_freight_cost:         toFloat(row.total_freight_cost),
    total_shipments:            toInteger(row.total_shipments),
    total_qty_shipped:          toFloat(row.total_qty_shipped),
    total_qty_received:         toFloat(row.total_qty_received),
    on_time_pct:                toFloat(row.on_time_pct)
}]->(d)
"""
load_to_neo4j(cypher_ships, ships_rows, label="SHIPS_TO relationships")
```

---

### 5.5 — HANDLED_BY: Carrier covers Warehouse → Destination route
**Source:** `fact_shipment` aggregated by `carrier_id + origin_warehouse_id + destination_id`

```python
# Cell 17 — HANDLED_BY relationship

df_handled = spark.sql("""
    SELECT
        carrier_id,
        origin_warehouse_id                         AS warehouse_id,
        destination_id,
        COUNT(*)                                    AS total_shipments,
        ROUND(AVG(transit_days_actual), 2)          AS avg_transit_days,
        ROUND(AVG(freight_cost), 2)                 AS avg_freight_cost,
        ROUND(
            SUM(CASE WHEN delivery_variance_days <= 0 THEN 1 ELSE 0 END)
            / COUNT(*) * 100,
        2)                                          AS on_time_pct,
        ROUND(AVG(delivery_variance_days), 2)       AS avg_delay_days
    FROM nike_databricks.cpg_supply_chain.fact_shipment
    GROUP BY carrier_id, origin_warehouse_id, destination_id
""")

handled_rows = df_handled.toPandas().to_dict("records")

cypher_handled = """
UNWIND $rows AS row
MATCH (ca:Carrier     {carrier_id:     row.carrier_id})
MATCH (d:Destination  {destination_id: row.destination_id})
CREATE (ca)-[:HANDLES_ROUTE {
    origin_warehouse_id: row.warehouse_id,
    total_shipments:     toInteger(row.total_shipments),
    avg_transit_days:    toFloat(row.avg_transit_days),
    avg_freight_cost:    toFloat(row.avg_freight_cost),
    on_time_pct:         toFloat(row.on_time_pct),
    avg_delay_days:      toFloat(row.avg_delay_days)
}]->(d)
"""
load_to_neo4j(cypher_handled, handled_rows, label="HANDLES_ROUTE relationships")
```

---

### 5.6 — DEMANDS: Customer → Product
**Source:** `fact_sales_demand` aggregated by `customer_id + product_id`

```python
# Cell 18 — DEMANDS relationship

df_demands = spark.sql("""
    SELECT
        customer_id,
        product_id,
        ROUND(SUM(units_demanded), 2)               AS total_units_demanded,
        ROUND(SUM(units_fulfilled), 2)              AS total_units_fulfilled,
        ROUND(AVG(fulfillment_rate_pct), 2)         AS avg_fulfillment_rate_pct,
        ROUND(SUM(revenue), 2)                      AS total_revenue,
        COUNT(*)                                    AS total_orders,
        ROUND(AVG(units_demanded), 2)               AS avg_order_size
    FROM nike_databricks.cpg_supply_chain.fact_sales_demand
    GROUP BY customer_id, product_id
""")

demands_rows = df_demands.toPandas().to_dict("records")

cypher_demands = """
UNWIND $rows AS row
MATCH (c:Customer {customer_id: row.customer_id})
MATCH (p:Product  {product_id:  row.product_id})
CREATE (c)-[:DEMANDS {
    total_units_demanded:    toFloat(row.total_units_demanded),
    total_units_fulfilled:   toFloat(row.total_units_fulfilled),
    avg_fulfillment_rate_pct: toFloat(row.avg_fulfillment_rate_pct),
    total_revenue:           toFloat(row.total_revenue),
    total_orders:            toInteger(row.total_orders),
    avg_order_size:          toFloat(row.avg_order_size)
}]->(p)
"""
load_to_neo4j(cypher_demands, demands_rows, label="DEMANDS relationships")
```

---

### 5.7 — ORDERS_TO: Customer → Destination
**Source:** `fact_sales_demand` aggregated by `customer_id + destination_id`

```python
# Cell 19 — ORDERS_TO relationship

df_orders_to = spark.sql("""
    SELECT
        customer_id,
        destination_id,
        COUNT(*)                        AS total_orders,
        ROUND(SUM(units_demanded), 2)   AS total_units,
        ROUND(SUM(revenue), 2)          AS total_revenue
    FROM nike_databricks.cpg_supply_chain.fact_sales_demand
    GROUP BY customer_id, destination_id
""")

orders_to_rows = df_orders_to.toPandas().to_dict("records")

cypher_orders_to = """
UNWIND $rows AS row
MATCH (c:Customer    {customer_id:    row.customer_id})
MATCH (d:Destination {destination_id: row.destination_id})
CREATE (c)-[:ORDERS_TO {
    total_orders:  toInteger(row.total_orders),
    total_units:   toFloat(row.total_units),
    total_revenue: toFloat(row.total_revenue)
}]->(d)
"""
load_to_neo4j(cypher_orders_to, orders_to_rows, label="ORDERS_TO relationships")
```

---

### 5.8 — ALTERNATIVE_FOR: Vendor → Vendor (Computed)
**Source:** Computed in Databricks — vendors sharing the same products

```python
# Cell 20 — ALTERNATIVE_FOR relationship (graph-native, no direct fact table)

df_alt = spark.sql("""
    WITH vendor_products AS (
        SELECT DISTINCT vendor_id, product_id
        FROM nike_databricks.cpg_supply_chain.fact_procurement
    ),
    vendor_overlap AS (
        SELECT
            a.vendor_id     AS vendor_id_a,
            b.vendor_id     AS vendor_id_b,
            COUNT(*)        AS shared_product_count
        FROM vendor_products a
        JOIN vendor_products b
          ON a.product_id = b.product_id
         AND a.vendor_id  != b.vendor_id
        GROUP BY a.vendor_id, b.vendor_id
    ),
    vendor_metrics AS (
        SELECT
            vendor_id,
            AVG(unit_cost)              AS avg_unit_cost,
            AVG(lead_time_days)         AS avg_lead_time,
            AVG(delivery_variance_pct)  AS avg_variance
        FROM nike_databricks.cpg_supply_chain.fact_procurement
        GROUP BY vendor_id
    )
    SELECT
        vo.vendor_id_a,
        vo.vendor_id_b,
        vo.shared_product_count,
        ROUND(vm_b.avg_unit_cost - vm_a.avg_unit_cost, 4)   AS cost_delta,
        ROUND(vm_b.avg_lead_time - vm_a.avg_lead_time, 2)   AS lead_time_delta_days,
        ROUND(vm_b.avg_variance  - vm_a.avg_variance,  2)   AS variance_delta,
        CASE
            WHEN vo.shared_product_count >= 5 THEN 'High'
            WHEN vo.shared_product_count >= 2 THEN 'Medium'
            ELSE 'Low'
        END AS substitution_confidence
    FROM vendor_overlap vo
    JOIN vendor_metrics vm_a ON vo.vendor_id_a = vm_a.vendor_id
    JOIN vendor_metrics vm_b ON vo.vendor_id_b = vm_b.vendor_id
""")

alt_rows = df_alt.toPandas().to_dict("records")

cypher_alt = """
UNWIND $rows AS row
MATCH (va:Vendor {vendor_id: row.vendor_id_a})
MATCH (vb:Vendor {vendor_id: row.vendor_id_b})
CREATE (vb)-[:ALTERNATIVE_FOR {
    shared_product_count:       toInteger(row.shared_product_count),
    cost_delta:                 toFloat(row.cost_delta),
    lead_time_delta_days:       toFloat(row.lead_time_delta_days),
    variance_delta:             toFloat(row.variance_delta),
    substitution_confidence:    row.substitution_confidence
}]->(va)
"""
load_to_neo4j(cypher_alt, alt_rows, label="ALTERNATIVE_FOR relationships")
```

---

## Section 6 — Full Validation in Neo4j Browser

Run all of these in **Neo4j Browser** after the ETL completes.

### 6.1 — Node count by label (should match Databricks row counts)

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS node_count
ORDER BY node_count DESC;
```

### 6.2 — Relationship count by type

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(r) AS count
ORDER BY count DESC;
```

### 6.3 — Spot check: a vendor and everything it connects to

```cypher
// Replace the vendor_name with one from your actual data
MATCH (v:Vendor {vendor_name: 'Your Vendor Name Here'})
OPTIONAL MATCH (v)-[s:SUPPLIES]->(p:Product)
OPTIONAL MATCH (v)-[a:ALTERNATIVE_FOR]->(v2:Vendor)
RETURN v, s, p, a, v2;
```

### 6.4 — Spot check: full supply chain path for one product

```cypher
// Shows the entire supply chain for one product
MATCH path = (v:Vendor)-[:SUPPLIES]->(p:Product {category: 'Family Care'})
             <-[:STOCKS]-(w:Warehouse)
             -[:SHIPS_TO]->(d:Destination)
             <-[:ORDERS_TO]-(c:Customer)
RETURN path
LIMIT 25;
```

### 6.5 — Visualize the schema after full load

```cypher
CALL db.schema.visualization();
```

This should now show all 9 node labels connected by all 7 relationship types.

---

## Section 7 — Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `Node with vendor_id already exists` | Forgot to delete Step 1 sample data | Run `MATCH (n) DETACH DELETE n` in Neo4j Browser |
| `MATCH found 0 nodes` on relationship load | Dimension load failed silently | Re-run Section 4 load for that dim, verify node count |
| `Connection refused: localhost:7687` | Neo4j Desktop instance not running | Open Desktop, click Start on the DBMS |
| `NullPointerException on toFloat(null)` | Fact table has NULL in a metric column | Add `COALESCE(column, 0.0)` in your Spark SQL |
| `toPandas()` memory error | Fact table is very large | Add `LIMIT 50000` to Spark SQL for PoC testing |
| Relationship count looks too low | Aggregation GROUP BY dropped some rows | Check for UUID type mismatch — cast to STRING in SQL |

---

## Section 8 — The Complete Notebook Structure (Summary)

```
notebook: 00_neo4j_connection_test.py
  └─ Cell 1: pip install neo4j
  └─ Cell 2: connection test

notebook: 01_load_dimensions.py
  └─ Cell 3:  Load Vendor
  └─ Cell 4:  Load Product
  └─ Cell 5:  Load Plant
  └─ Cell 6:  Load Warehouse
  └─ Cell 7:  Load Customer
  └─ Cell 8:  Load Carrier
  └─ Cell 9:  Load Destination
  └─ Cell 10: Load Shift
  └─ Cell 11: Verify node counts

notebook: 02_load_relationships.py
  └─ Cell 1:  SUPPLIES       (Vendor → Product)
  └─ Cell 2:  PRODUCES       (Plant → Product)
  └─ Cell 3:  STOCKS         (Warehouse → Product)
  └─ Cell 4:  SHIPS_TO       (Warehouse → Destination)
  └─ Cell 5:  HANDLES_ROUTE  (Carrier → Destination)
  └─ Cell 6:  DEMANDS        (Customer → Product)
  └─ Cell 7:  ORDERS_TO      (Customer → Destination)
  └─ Cell 8:  ALTERNATIVE_FOR (Vendor → Vendor)
  └─ Cell 9:  Verify relationship counts
```

---

## What You Have After This Step

```
Neo4j local instance contains:
  ✅ All dimension entities as typed nodes with full properties
  ✅ All fact table metrics as aggregated relationship properties
  ✅ Graph-native ALTERNATIVE_FOR vendor substitution links
  ✅ Full supply chain traversable:
     Vendor → Product ← Plant
                ↑
            Warehouse → Destination ← Customer
                ↑
             Carrier
```

**Next Step Preview — Step 3:**
Graph Enrichment: compute risk flags, centrality scores,
single-source vendor detection, and stockout propagation signals
directly in Cypher. These become the inputs your AI agents reason over.
```
