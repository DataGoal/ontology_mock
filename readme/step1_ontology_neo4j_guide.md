# Step 1: Define the Ontology in Neo4j Desktop
## CPG Supply Chain Knowledge Graph — Hands-On Guide

> **Pre-requisite:** Neo4j Desktop is installed, a local DBMS is created, and you have
> opened the **Neo4j Browser** (the query interface inside Neo4j Desktop).
> All commands below are run inside that Browser, one block at a time.

---

## What You Are Building

Before touching Neo4j, understand the mental model shift:

| Concept in Databricks | Equivalent in Neo4j |
|---|---|
| Table | Node Label (e.g., `Vendor`, `Product`) |
| Row | Node instance |
| Foreign Key join | Relationship (e.g., `-[:SUPPLIES]->`) |
| Column | Property on a Node or Relationship |
| Schema / DDL | Constraints + Indexes |

In a graph database, **the relationships are first-class citizens** — not joins you compute at query time. This is the fundamental difference.

---

## Phase 1 — Understand the Neo4j Browser UI

When you open Neo4j Browser you will see:
- A **top bar** with a `$` prompt — this is where you type Cypher queries
- A **results panel** below — shows graph visualizations or table output
- A left sidebar with saved scripts, schema info, etc.

**The most important shortcut:** `Ctrl+Enter` (or `Cmd+Enter` on Mac) runs the query.

To run a multi-statement script, you need to prefix it with `:` commands or run statements one at a time. We will run them **one block at a time** throughout this guide.

---

## Phase 2 — Drop Everything First (Clean Slate)

If you have been experimenting, start clean. Run this:

```cypher
// WARNING: Deletes ALL nodes and relationships in the database
// Only run this on your local dev instance
MATCH (n) DETACH DELETE n;
```

Then verify it is empty:

```cypher
MATCH (n) RETURN count(n) AS total_nodes;
// Should return 0
```

---

## Phase 3 — Create Constraints (This IS Your Schema / DDL)

### What is a Constraint in Neo4j?

A **constraint** does two things simultaneously:
1. Enforces uniqueness (like a PRIMARY KEY in SQL)
2. Automatically creates an **index** on that property (fast lookups)

Think of it as: `ALTER TABLE vendor ADD CONSTRAINT pk_vendor PRIMARY KEY (vendor_id);`

**Run each block below one at a time. Paste into the browser prompt and hit Ctrl+Enter.**

---

### 3.1 — Dimension Node Constraints

```cypher
// VENDOR — master for suppliers, co-packers, 3PL
CREATE CONSTRAINT constraint_vendor_id IF NOT EXISTS
FOR (v:Vendor)
REQUIRE v.vendor_id IS UNIQUE;
```

```cypher
// PRODUCT — SKU master across all CPG categories
CREATE CONSTRAINT constraint_product_id IF NOT EXISTS
FOR (p:Product)
REQUIRE p.product_id IS UNIQUE;
```

```cypher
// PRODUCT SKU must also be unique (business key)
CREATE CONSTRAINT constraint_product_sku IF NOT EXISTS
FOR (p:Product)
REQUIRE p.sku IS UNIQUE;
```

```cypher
// PLANT — manufacturing and conversion facilities
CREATE CONSTRAINT constraint_plant_id IF NOT EXISTS
FOR (pl:Plant)
REQUIRE pl.plant_id IS UNIQUE;
```

```cypher
// PLANT CODE must be unique (business key)
CREATE CONSTRAINT constraint_plant_code IF NOT EXISTS
FOR (pl:Plant)
REQUIRE pl.plant_code IS UNIQUE;
```

```cypher
// WAREHOUSE — DCs, raw material stores, cross-dock
CREATE CONSTRAINT constraint_warehouse_id IF NOT EXISTS
FOR (w:Warehouse)
REQUIRE w.warehouse_id IS UNIQUE;
```

```cypher
// WAREHOUSE CODE must be unique (business key)
CREATE CONSTRAINT constraint_warehouse_code IF NOT EXISTS
FOR (w:Warehouse)
REQUIRE w.warehouse_code IS UNIQUE;
```

```cypher
// CUSTOMER — retail and B2B customer master
CREATE CONSTRAINT constraint_customer_id IF NOT EXISTS
FOR (c:Customer)
REQUIRE c.customer_id IS UNIQUE;
```

```cypher
// CARRIER — logistics provider master
CREATE CONSTRAINT constraint_carrier_id IF NOT EXISTS
FOR (ca:Carrier)
REQUIRE ca.carrier_id IS UNIQUE;
```

```cypher
// DESTINATION — delivery endpoints (retail stores, DCs, 3PLs)
CREATE CONSTRAINT constraint_destination_id IF NOT EXISTS
FOR (d:Destination)
REQUIRE d.destination_id IS UNIQUE;
```

```cypher
// SHIFT — manufacturing shift definitions
CREATE CONSTRAINT constraint_shift_id IF NOT EXISTS
FOR (s:Shift)
REQUIRE s.shift_id IS UNIQUE;
```

```cypher
// DATE — calendar dimension
CREATE CONSTRAINT constraint_date_id IF NOT EXISTS
FOR (dt:Date)
REQUIRE dt.date_id IS UNIQUE;
```

```cypher
// DATE full_date must be unique (one node per calendar day)
CREATE CONSTRAINT constraint_date_fulldate IF NOT EXISTS
FOR (dt:Date)
REQUIRE dt.full_date IS UNIQUE;
```

---

### 3.2 — Verify All Constraints Were Created

```cypher
SHOW CONSTRAINTS;
```

You should see **13 constraints** listed. Each row shows the label, property, and constraint type. If any are missing, re-run that specific block.

---

## Phase 4 — Create Additional Indexes

Constraints already index the primary key properties. But your agents will also filter nodes by properties like `region`, `active`, `reliability_score`, `category`. Add lookup indexes for these.

### Why this matters for agents:
When an agent asks "find all active Tier 1 vendors in APAC", Neo4j will do a full scan of all Vendor nodes unless an index exists. With millions of nodes this is slow.

```cypher
// Vendor — agents frequently filter by region, tier, active status
CREATE INDEX index_vendor_region IF NOT EXISTS
FOR (v:Vendor) ON (v.region);
```

```cypher
CREATE INDEX index_vendor_tier IF NOT EXISTS
FOR (v:Vendor) ON (v.tier);
```

```cypher
CREATE INDEX index_vendor_active IF NOT EXISTS
FOR (v:Vendor) ON (v.active);
```

```cypher
// Product — agents filter by category and brand
CREATE INDEX index_product_category IF NOT EXISTS
FOR (p:Product) ON (p.category);
```

```cypher
CREATE INDEX index_product_brand IF NOT EXISTS
FOR (p:Product) ON (p.brand);
```

```cypher
CREATE INDEX index_product_active IF NOT EXISTS
FOR (p:Product) ON (p.active);
```

```cypher
// Plant — agents filter by region and plant_type
CREATE INDEX index_plant_region IF NOT EXISTS
FOR (pl:Plant) ON (pl.region);
```

```cypher
CREATE INDEX index_plant_type IF NOT EXISTS
FOR (pl:Plant) ON (pl.plant_type);
```

```cypher
// Warehouse — agents filter by region and type
CREATE INDEX index_warehouse_region IF NOT EXISTS
FOR (w:Warehouse) ON (w.region);
```

```cypher
CREATE INDEX index_warehouse_type IF NOT EXISTS
FOR (w:Warehouse) ON (w.type);
```

```cypher
// Customer — agents filter by segment and channel
CREATE INDEX index_customer_segment IF NOT EXISTS
FOR (c:Customer) ON (c.customer_segment);
```

```cypher
CREATE INDEX index_customer_channel IF NOT EXISTS
FOR (c:Customer) ON (c.channel);
```

```cypher
// Carrier — agents filter by carrier_type
CREATE INDEX index_carrier_type IF NOT EXISTS
FOR (ca:Carrier) ON (ca.carrier_type);
```

```cypher
// Destination — agents filter by region and type
CREATE INDEX index_destination_region IF NOT EXISTS
FOR (d:Destination) ON (d.region);
```

```cypher
// Date — agents filter by year, month, quarter
CREATE INDEX index_date_year IF NOT EXISTS
FOR (dt:Date) ON (dt.year);
```

```cypher
CREATE INDEX index_date_month IF NOT EXISTS
FOR (dt:Date) ON (dt.month);
```

### Verify all indexes:

```cypher
SHOW INDEXES;
```

You should see your 13 constraint-based indexes PLUS the 16 additional ones above.

---

## Phase 5 — Define the Relationship Types (The Ontology Core)

This is the most important step. In Neo4j, relationships don't need a separate "CREATE" statement to define them — they are defined **by the act of creating them**. But we document them here as your ontology contract.

Here's what each relationship means and what properties live **on the relationship** (not on the nodes):

### The Full Relationship Map

```
(Vendor)       -[:SUPPLIES]->          (Product)
(Plant)        -[:PRODUCES]->          (Product)
(Warehouse)    -[:STOCKS]->            (Product)
(Warehouse)    -[:SHIPS_TO]->          (Destination)
(Carrier)      -[:HANDLES_ROUTE]->     (Destination)
(Customer)     -[:DEMANDS]->           (Product)
(Customer)     -[:ORDERS_TO]->         (Destination)
(Vendor)       -[:ALTERNATIVE_FOR]->   (Vendor)      [computed, no direct source table]
```

### Why relationships carry properties

In your star schema, fact table columns are the measurements. In the graph, those measurements become **properties on the relationship** — because the measurement belongs to the *connection*, not to either entity alone.

Example: `unit_cost` doesn't belong to Vendor or Product alone. It belongs to *"this vendor supplying this product"* — so it lives on `[:SUPPLIES]`.

---

## Phase 6 — Create Sample/Test Nodes to Validate the Schema

Now insert a small sample to confirm everything works before your ETL pipeline runs.

### 6.1 — Create one Vendor node

```cypher
CREATE (v:Vendor {
  vendor_id:          'v-001',
  vendor_name:        'Acme Pulp & Paper Co.',
  vendor_type:        'Raw Material',
  country:            'USA',
  region:             'North America',
  tier:               'Tier 1',
  reliability_score:  0.92,
  avg_lead_time_days: 14.0,
  active:             true
})
RETURN v;
```

### 6.2 — Create one Product node

```cypher
CREATE (p:Product {
  product_id:       'p-001',
  sku:              'KC-TISSUE-48-ROLL',
  product_name:     'Kleenex Tissue 48-Roll Pack',
  category:         'Family Care',
  sub_category:     'Facial Tissue',
  brand:            'Kleenex',
  unit_weight_kg:   2.4,
  packaging_type:   'Box',
  active:           true
})
RETURN p;
```

### 6.3 — Create one Warehouse node

```cypher
CREATE (w:Warehouse {
  warehouse_id:            'wh-001',
  warehouse_name:          'Memphis Distribution Center',
  warehouse_code:          'MEM-DC-01',
  type:                    'Finished Goods',
  country:                 'USA',
  region:                  'North America',
  storage_capacity_units:  500000.0,
  active:                  true
})
RETURN w;
```

### 6.4 — Create one Plant node

```cypher
CREATE (pl:Plant {
  plant_id:                'pl-001',
  plant_name:              'Ogden Manufacturing Plant',
  plant_code:              'OGD-MFG-01',
  country:                 'USA',
  region:                  'North America',
  capacity_units_per_day:  120000.0,
  plant_type:              'Fabrication',
  active:                  true
})
RETURN pl;
```

### 6.5 — Create one Customer node

```cypher
CREATE (c:Customer {
  customer_id:       'cu-001',
  customer_name:     'Walmart Inc.',
  customer_segment:  'Retail',
  country:           'USA',
  region:            'North America',
  channel:           'Direct',
  active:            true
})
RETURN c;
```

### 6.6 — Create one Carrier node

```cypher
CREATE (ca:Carrier {
  carrier_id:              'ca-001',
  carrier_name:            'FedEx Freight',
  carrier_type:            'Road',
  country:                 'USA',
  avg_transit_days:        3.5,
  on_time_delivery_pct:    94.2,
  active:                  true
})
RETURN ca;
```

### 6.7 — Create one Destination node

```cypher
CREATE (d:Destination {
  destination_id:    'dest-001',
  destination_name:  'Walmart DC Bentonville',
  destination_type:  'Customer DC',
  country:           'USA',
  region:            'North America',
  lat:               36.3729,
  lon:               -94.2088
})
RETURN d;
```

---

## Phase 7 — Create Relationships with Properties

This is where the graph comes alive. We connect the sample nodes above with **relationships that carry measurement properties from your fact tables**.

### 7.1 — Vendor SUPPLIES Product
(Properties come from `fact_procurement` aggregated)

```cypher
MATCH (v:Vendor {vendor_id: 'v-001'})
MATCH (p:Product {product_id: 'p-001'})
CREATE (v)-[:SUPPLIES {
  // Aggregated from fact_procurement
  avg_unit_cost:              4.25,
  avg_lead_time_days:         14.0,
  avg_delivery_variance_pct:  -2.1,
  total_orders_count:         48,
  last_order_status:          'Received',
  // Computed risk signal
  under_delivery_flag:        false
}]->(p)
RETURN v, p;
```

### 7.2 — Plant PRODUCES Product
(Properties come from `fact_manufacturing` aggregated)

```cypher
MATCH (pl:Plant {plant_id: 'pl-001'})
MATCH (p:Product {product_id: 'p-001'})
CREATE (pl)-[:PRODUCES {
  // Aggregated from fact_manufacturing
  avg_units_planned:          95000.0,
  avg_units_produced:         91200.0,
  avg_defect_rate_pct:        1.8,
  avg_throughput_rate:        3800.0,
  avg_machine_utilization_pct: 76.5,
  avg_downtime_hours:         0.9
}]->(p)
RETURN pl, p;
```

### 7.3 — Warehouse STOCKS Product
(Properties come from `fact_inventory` — latest snapshot)

```cypher
MATCH (w:Warehouse {warehouse_id: 'wh-001'})
MATCH (p:Product {product_id: 'p-001'})
CREATE (w)-[:STOCKS {
  // From latest fact_inventory snapshot
  stock_on_hand:    42000.0,
  reorder_point:    15000.0,
  safety_stock:     8000.0,
  stockout_flag:    0.0,
  overstock_flag:   0.0,
  snapshot_date:    '2025-04-01'
}]->(p)
RETURN w, p;
```

### 7.4 — Warehouse SHIPS_TO Destination
(Properties come from `fact_shipment` aggregated)

```cypher
MATCH (w:Warehouse {warehouse_id: 'wh-001'})
MATCH (d:Destination {destination_id: 'dest-001'})
CREATE (w)-[:SHIPS_TO {
  // Aggregated from fact_shipment
  avg_freight_cost:            1850.0,
  avg_transit_days_actual:     3.8,
  avg_transit_days_expected:   3.5,
  avg_delivery_variance_days:  0.3,
  total_shipments:             124,
  on_time_pct:                 91.9
}]->(d)
RETURN w, d;
```

### 7.5 — Customer DEMANDS Product
(Properties come from `fact_sales_demand` aggregated)

```cypher
MATCH (c:Customer {customer_id: 'cu-001'})
MATCH (p:Product {product_id: 'p-001'})
CREATE (c)-[:DEMANDS {
  // Aggregated from fact_sales_demand
  avg_units_demanded:      85000.0,
  avg_units_fulfilled:     82450.0,
  avg_fulfillment_rate_pct: 97.0,
  total_revenue:           349400.0,
  period:                  '2025-Q1'
}]->(p)
RETURN c, p;
```

### 7.6 — Carrier HANDLES_ROUTE (Carrier → Destination)
(This is a new relationship not in the star schema — graph-native enrichment)

```cypher
MATCH (ca:Carrier {carrier_id: 'ca-001'})
MATCH (w:Warehouse {warehouse_id: 'wh-001'})
MATCH (d:Destination {destination_id: 'dest-001'})
CREATE (ca)-[:HANDLES_ROUTE {
  origin_warehouse_id:  'wh-001',
  avg_transit_days:     3.5,
  on_time_delivery_pct: 94.2,
  freight_cost_per_unit: 0.18
}]->(d)
RETURN ca, w, d;
```

### 7.7 — ALTERNATIVE_FOR (Graph-Native — No Source Table)
This relationship does not exist in your Databricks schema. It is computed based on vendor overlap on shared products. This is graph-only intelligence.

```cypher
// First create a second vendor to demonstrate
CREATE (v2:Vendor {
  vendor_id:          'v-002',
  vendor_name:        'Pacific Fiber Group',
  vendor_type:        'Raw Material',
  country:            'USA',
  region:             'North America',
  tier:               'Tier 2',
  reliability_score:  0.81,
  avg_lead_time_days: 18.0,
  active:             true
});
```

```cypher
// Also make v2 supply the same product
MATCH (v2:Vendor {vendor_id: 'v-002'})
MATCH (p:Product {product_id: 'p-001'})
CREATE (v2)-[:SUPPLIES {
  avg_unit_cost: 3.95,
  avg_lead_time_days: 18.0,
  avg_delivery_variance_pct: -5.2,
  total_orders_count: 12,
  last_order_status: 'Received',
  under_delivery_flag: true
}]->(p);
```

```cypher
// Now create the ALTERNATIVE_FOR relationship
MATCH (v1:Vendor {vendor_id: 'v-001'})
MATCH (v2:Vendor {vendor_id: 'v-002'})
CREATE (v2)-[:ALTERNATIVE_FOR {
  // Properties that help agents decide substitutability
  shared_product_count:    1,
  cost_delta_pct:          -7.1,       // v2 is 7.1% cheaper
  lead_time_delta_days:    4.0,        // v2 is 4 days slower
  reliability_delta:       -0.11,      // v2 is less reliable
  substitution_risk:       'Medium',
  computed_on:             '2025-04-01'
}]->(v1)
RETURN v1, v2;
```

---

## Phase 8 — Validate the Full Graph

### 8.1 — View the entire sample graph visually

```cypher
MATCH (n)-[r]->(m)
RETURN n, r, m;
```

In Neo4j Browser, this renders as an **interactive graph visualization**. Click any node to see its properties. Click any edge to see relationship properties.

### 8.2 — Count all nodes by label

```cypher
CALL apoc.meta.stats()
YIELD labels
RETURN labels;
```

If APOC is not installed (check below), use this instead:

```cypher
MATCH (n)
RETURN labels(n) AS label, count(n) AS count
ORDER BY count DESC;
```

### 8.3 — Check the schema visually

```cypher
CALL db.schema.visualization();
```

This is the single most useful command for a Neo4j beginner. It renders a **diagram of all node labels and relationship types** — your ontology map. Run this after every major change.

### 8.4 — Confirm relationship types exist

```cypher
CALL db.relationshipTypes();
```

Expected output:
- SUPPLIES
- PRODUCES
- STOCKS
- SHIPS_TO
- DEMANDS
- HANDLES_ROUTE
- ORDERS_TO
- ALTERNATIVE_FOR

---

## Phase 9 — Install APOC Plugin (Required for Later Steps)

APOC (Awesome Procedures on Cypher) is the standard Neo4j extension library. You will need it for ETL, data enrichment, and graph algorithms.

**Steps in Neo4j Desktop:**
1. Click on your project in the left panel
2. Click on your DBMS (local instance)
3. Click the **three-dot menu** → **Plugins**
4. Find **APOC** → click **Install**
5. **Restart** the database after install

Verify it works:

```cypher
RETURN apoc.version();
```

---

## Phase 10 — Add Ontology Metadata Nodes (Optional but Recommended)

This is an advanced pattern — storing the ontology itself inside the graph. It helps when AI agents need to understand what the graph contains before querying it.

```cypher
// Create a metadata node that describes the ontology
CREATE (meta:OntologyMeta {
  name:           'CPG Supply Chain Ontology',
  version:        '1.0.0',
  domain:         'Consumer Packaged Goods',
  created_date:   '2025-04-01',
  node_types:     ['Vendor','Product','Plant','Warehouse','Customer','Carrier','Destination','Shift','Date'],
  relationship_types: ['SUPPLIES','PRODUCES','STOCKS','SHIPS_TO','HANDLES_ROUTE','DEMANDS','ORDERS_TO','ALTERNATIVE_FOR'],
  source_schema:  'schema.yaml',
  description:    'Star schema converted to property graph for supply chain AI agents'
})
RETURN meta;
```

---

## Summary: What You Have Built

After completing all phases, your Neo4j local instance contains:

```
CONSTRAINTS (13):    Uniqueness enforcement on all primary keys + business keys
INDEXES (29):        Fast lookup by PK + common filter properties
NODE LABELS (9):     Vendor, Product, Plant, Warehouse, Customer,
                     Carrier, Destination, Shift, Date
RELATIONSHIP TYPES:
  [:SUPPLIES]          Vendor → Product      (procurement metrics as properties)
  [:PRODUCES]          Plant → Product       (manufacturing KPIs as properties)
  [:STOCKS]            Warehouse → Product   (inventory snapshot as properties)
  [:SHIPS_TO]          Warehouse → Dest      (shipment performance as properties)
  [:DEMANDS]           Customer → Product    (fulfillment metrics as properties)
  [:HANDLES_ROUTE]     Carrier → Dest        (transit SLA as properties)
  [:ORDERS_TO]         Customer → Dest       (order destination as properties)
  [:ALTERNATIVE_FOR]   Vendor → Vendor       (computed substitution score)

SAMPLE DATA:          2 Vendors, 1 Product, 1 Plant, 1 Warehouse,
                      1 Customer, 1 Carrier, 1 Destination
                      + all relationships connecting them
```

---

## What NOT to Do (Common Neo4j Beginner Mistakes)

| Mistake | Why It's a Problem | Correct Approach |
|---|---|---|
| Using `CREATE` instead of `MERGE` for ETL | Creates duplicate nodes every run | Always use `MERGE` in ETL |
| Putting ALL fact table columns on nodes | Nodes become huge, queries slow | Aggregate facts → relationship properties |
| Creating a `Date` node for every fact row | Millions of date nodes, poor performance | One `Date` node per calendar day, reuse via MERGE |
| Skipping constraints before loading data | Duplicate nodes guaranteed | Always run Phase 3 before any data load |
| Naming relationships as nouns (`SUPPLY`) | Reads unnaturally in traversals | Use verbs (`SUPPLIES`, `PRODUCES`, `DEMANDS`) |

---

## Next Step Preview: Step 2 — ETL Pipeline (Databricks → Neo4j)

Once you are satisfied with this ontology definition on your sample data, the next step is writing the PySpark / Python notebooks in Databricks that:

1. Read from your Delta tables
2. Aggregate fact table metrics per dimension combination
3. Use the `neo4j` Python driver with `MERGE` statements to load at scale
4. Schedule incremental loads via Delta Change Data Feed

Keep this guide open alongside Neo4j Browser as you work through it.
