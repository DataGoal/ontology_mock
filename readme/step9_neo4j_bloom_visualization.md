# Step 9: Neo4j Bloom Visualization
## CPG Supply Chain Knowledge Graph — Interactive Graph Visualization

> **What this step builds:** Five purpose-built Bloom Perspectives that
> let you visually explore your enriched supply chain graph — no code
> required. Each Perspective is a curated view of the graph for a
> specific use case: risk monitoring, inventory health, manufacturing
> performance, supply chain paths, and anomaly investigation.
> Everything in this step is done inside the **Bloom UI** that ships
> with Neo4j Aura Free Tier.

---

## What Neo4j Bloom Is

Bloom is Neo4j's built-in graph visualization tool. Think of it as
a visual query interface — instead of writing Cypher you click, search,
and explore. It is already available on your Aura Free Tier instance
at no extra cost.

```
Bloom is NOT a BI dashboard (that's Power BI / Step 9B)
Bloom IS a graph exploration tool — best for:
  • Seeing relationship patterns visually
  • Investigating a specific vendor / product path
  • Demonstrating graph intelligence to stakeholders
  • Exploring "why" a risk signal exists by following edges
```

---

## Architecture: Where Bloom Sits

```
VISUALIZATION & CONSUMPTION LAYER (your architecture diagram)
  ┌──────────────┐   ┌───────────────────────────┐   ┌──────────────┐
  │  Dashboard   │   │  Graph Visualization       │   │  Alerting    │
  │  Power BI /  │   │  Neo4j Bloom  ← THIS STEP  │   │  Slack/Email │
  │  custom UI   │   │                            │   │              │
  └──────────────┘   └───────────────────────────┘   └──────────────┘
                                   │
                                   ▼
                    Reads directly from Neo4j Aura
                    (your enriched graph from Steps 1-3)
                    No additional setup — already connected
```

---

## Before You Start — Checklist

```
✅ Steps 1-6A complete — graph enriched with risk signals
✅ Neo4j Aura Free Tier instance is RUNNING
✅ You can reach the Aura console at console.neo4j.io
✅ Modern browser (Chrome or Edge recommended for Bloom)

No Python. No code. No installs.
Everything in this step happens in your browser.
```

---

## Section 1 — Open Neo4j Bloom

### 1.1 — Launch Bloom from Aura console

1. Go to **console.neo4j.io**
2. Click your instance (the one with your supply chain graph)
3. Click the **blue "Open" button** → choose **"Explore"**
   (some versions show this as "Neo4j Bloom")
4. Bloom opens in a new browser tab connected to your Aura instance
5. Sign in with your Aura credentials if prompted

You will land on the **Bloom Home Screen** which shows:
- A search bar at the top
- A canvas (empty dark area) in the centre
- A left panel with Perspectives
- A bottom panel with saved searches

### 1.2 — Understand the Bloom UI layout

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 Search bar                          ⚙️ Settings  [+]    │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                   │
│  LEFT    │           CANVAS                                  │
│  PANEL   │   (nodes and relationships render here)          │
│          │                                                   │
│  • Persp │                                                   │
│  • Rules │                                                   │
│  • Filter│                                                   │
│          │                                                   │
├──────────┴──────────────────────────────────────────────────┤
│  SAVED SEARCHES / SCENE ACTIONS                             │
└─────────────────────────────────────────────────────────────┘
```

Key terms you need to know:
- **Perspective** — a saved configuration: which node labels to show,
  what colours/sizes to use, what search phrases are available
- **Scene** — what is currently visible on the canvas
- **Rule** — a conditional style (e.g. red if `risk_flag = true`)
- **Search Phrase** — a natural language shortcut that runs a
  pre-defined Cypher query

---

## Section 2 — Create the Base Perspective

A Perspective controls what your graph looks like. We create one
master Perspective first and configure all five views within it.

### 2.1 — Create a new Perspective

1. In the left panel click **"Perspectives"** (the layers icon)
2. Click **"+ New Perspective"**
3. Name it: `CPG Supply Chain`
4. Click **"Generate Perspective"** — Bloom auto-discovers your
   node labels from the graph
5. You should see all 9 labels listed:
   `Vendor, Product, Plant, Warehouse, Customer, Carrier,
    Destination, Shift, Date, KnowledgeChunk`
6. Click **"Save"**

### 2.2 — Set node display names

For each label, configure what text appears on the node in the canvas:

| Node Label | Set "Display Name" property to |
|---|---|
| Vendor | `vendor_name` |
| Product | `product_name` |
| Plant | `plant_name` |
| Warehouse | `warehouse_name` |
| Customer | `customer_name` |
| Carrier | `carrier_name` |
| Destination | `destination_name` |

**How to set:**
1. In left panel → click a label (e.g. `Vendor`)
2. Click **"Display Name"** dropdown
3. Select `vendor_name` from the property list
4. Repeat for each label

### 2.3 — Assign base colours by entity type

Click each label and set a distinct colour so entities are visually
distinguishable at a glance:

| Node Label | Colour | Hex Code |
|---|---|---|
| Vendor | Orange | `#fa6800` |
| Product | Purple | `#7B6FBF` |
| Plant | Blue | `#1ba1e2` |
| Warehouse | Teal | `#1A7A5E` |
| Customer | Gold | `#f0a30a` |
| Carrier | Pink | `#d80073` |
| Destination | Grey | `#6b7280` |
| KnowledgeChunk | Light grey | `#d1d5db` |

**How to set:**
1. Click a label in the left panel
2. Click the **colour circle** next to the label name
3. Enter the hex code or pick from the colour wheel
4. Click **"Save"**

---

## Section 3 — Configure Node Style Rules

Style rules are the most powerful Bloom feature for your use case.
They change a node's colour, size, or icon based on its property values —
so risk signals computed in Step 3 become visible without any searching.

### 3.1 — Vendor risk rules

**How to create a rule:**
1. Click `Vendor` label in left panel
2. Click **"Rules"** tab
3. Click **"+ Add Rule"**
4. Set: Property = `risk_flag`, Operator = `=`, Value = `true`
5. Set style: Colour = **Red** (`#ef4444`), Size = **Large**
6. Name it: `Vendor at Risk`
7. Click **Save**

Create these rules for Vendor nodes:

| Rule Name | Property | Operator | Value | Colour | Size |
|---|---|---|---|---|---|
| `Critical Vendor` | `reliability_tier` | `=` | `CRITICAL` | `#dc2626` (dark red) | Extra Large |
| `At Risk Vendor` | `reliability_tier` | `=` | `AT_RISK` | `#f97316` (orange) | Large |
| `Good Vendor` | `reliability_tier` | `=` | `GOOD` | `#22c55e` (green) | Medium |
| `Excellent Vendor` | `reliability_tier` | `=` | `EXCELLENT` | `#16a34a` (dark green) | Small |
| `Single Source` | `single_source_product_count` | `>` | `0` | `#eab308` (yellow) | Large |
| `Stockout Escalation` | `stockout_escalation_flag` | `=` | `true` | `#dc2626` (dark red) | Extra Large |

> **Rule priority:** Rules are applied top-to-bottom — put `Critical Vendor`
> first so it overrides `At Risk Vendor` when both conditions are true.
> Drag rules to reorder them.

### 3.2 — Product vulnerability rules

Click `Product` label → Rules tab → Add rules:

| Rule Name | Property | Operator | Value | Colour | Size |
|---|---|---|---|---|---|
| `Compounded Risk` | `compounded_risk_flag` | `=` | `true` | `#dc2626` (dark red) | Extra Large |
| `Active Stockout` | `has_any_stockout` | `=` | `true` | `#f97316` (orange) | Large |
| `Single Source Risk` | `single_source_risk` | `=` | `true` | `#eab308` (yellow) | Large |
| `Demand Pressure` | `demand_pressure_flag` | `=` | `true` | `#fb923c` (light orange) | Medium |
| `Critical Network` | `network_criticality` | `=` | `CRITICAL` | `#9333ea` (purple) | Extra Large |

### 3.3 — Plant performance rules

Click `Plant` label → Rules tab → Add rules:

| Rule Name | Property | Operator | Value | Colour | Size |
|---|---|---|---|---|---|
| `Over Capacity` | `utilization_status` | `=` | `OVER_CAPACITY` | `#dc2626` (red) | Extra Large |
| `High Defect Rate` | `avg_defect_rate_pct` | `>` | `5` | `#f97316` (orange) | Large |
| `Underutilized` | `utilization_status` | `=` | `CRITICALLY_UNDERUTILIZED` | `#6b7280` (grey) | Small |
| `Healthy Plant` | `performance_flag` | `=` | `false` | `#22c55e` (green) | Medium |

### 3.4 — Warehouse health rules

Click `Warehouse` label → Rules tab → Add rules:

| Rule Name | Property | Operator | Value | Colour | Size |
|---|---|---|---|---|---|
| `Stockout Active` | `stockout_sku_count` | `>` | `0` | `#dc2626` (red) | Extra Large |
| `Over Capacity` | `capacity_status` | `=` | `OVER_CAPACITY` | `#f97316` (orange) | Large |
| `Bottleneck` | `is_bottleneck_warehouse` | `=` | `true` | `#eab308` (yellow) | Large |
| `Major Hub` | `hub_tier` | `=` | `MAJOR_HUB` | `#1d4ed8` (blue) | Extra Large |
| `Healthy` | `health_flag` | `=` | `false` | `#22c55e` (green) | Medium |

### 3.5 — Carrier performance rules

Click `Carrier` label → Rules tab → Add rules:

| Rule Name | Property | Operator | Value | Colour | Size |
|---|---|---|---|---|---|
| `Underperforming` | `performance_tier` | `=` | `UNDERPERFORMING` | `#dc2626` (red) | Large |
| `At Risk Carrier` | `performance_tier` | `=` | `AT_RISK` | `#f97316` (orange) | Medium |
| `Premium Carrier` | `performance_tier` | `=` | `PREMIUM` | `#22c55e` (green) | Medium |

### 3.6 — Customer risk rules

Click `Customer` label → Rules tab → Add rules:

| Rule Name | Property | Operator | Value | Colour | Size |
|---|---|---|---|---|---|
| `VIP at Risk` | `vip_at_risk_flag` | `=` | `true` | `#dc2626` (red) | Extra Large |
| `Key Account` | `revenue_tier` | `=` | `TIER_1_KEY_ACCOUNT` | `#f0a30a` (gold) | Large |
| `Fulfillment Risk` | `fulfillment_risk_flag` | `=` | `true` | `#f97316` (orange) | Medium |

---

## Section 4 — Configure Relationship Style Rules

Style relationships so their visual weight reflects risk level.

### 4.1 — SUPPLIES relationship rules

1. In left panel → click **"Relationship Types"**
2. Click `SUPPLIES`
3. Click **"Rules"** tab → **"+ Add Rule"**

| Rule Name | Property | Operator | Value | Colour | Width |
|---|---|---|---|---|---|
| `Under Delivery` | `under_delivery_flag` | `=` | `true` | `#dc2626` (red) | Thick |
| `Healthy Supply` | `under_delivery_flag` | `=` | `false` | `#22c55e` (green) | Normal |

### 4.2 — SHIPS_TO relationship rules

Click `SHIPS_TO` → Rules tab:

| Rule Name | Property | Operator | Value | Colour | Width |
|---|---|---|---|---|---|
| `High Risk Route` | `route_risk_level` | `=` | `HIGH_RISK` | `#dc2626` (red) | Thick |
| `Medium Risk Route` | `route_risk_level` | `=` | `MEDIUM_RISK` | `#f97316` (orange) | Medium |
| `On Time Route` | `route_risk_level` | `=` | `ON_TIME` | `#22c55e` (green) | Thin |

### 4.3 — ALTERNATIVE_FOR relationship rules

Click `ALTERNATIVE_FOR` → Rules tab:

| Rule Name | Property | Operator | Value | Colour | Width |
|---|---|---|---|---|---|
| `HIGH Priority Alt` | `recommendation_priority` | `=` | `HIGH` | `#22c55e` (green) | Thick |
| `MEDIUM Priority Alt` | `recommendation_priority` | `=` | `MEDIUM` | `#eab308` (yellow) | Medium |
| `LOW Priority Alt` | `recommendation_priority` | `=` | `LOW` | `#6b7280` (grey) | Thin |

---

## Section 5 — Create Search Phrases

Search Phrases are the killer feature for PoC demos. They let anyone
type a plain English phrase in the Bloom search bar and immediately
get a relevant subgraph — no Cypher knowledge needed.

**How to create a Search Phrase:**
1. Click the **search bar** at the top of Bloom
2. Click **"Saved Searches"** or the bookmark icon
3. Click **"+ New Saved Search"**
4. Give it a Name (the phrase the user types) and a Cypher query
5. Click **Save**

Create all of the following:

---

### 5.1 — Vendor Risk Phrases

**Phrase:** `Show critical vendors`
```cypher
MATCH (v:Vendor)
WHERE v.reliability_tier = 'CRITICAL'
   OR v.risk_score >= 60
RETURN v
ORDER BY v.risk_score DESC
LIMIT 20
```

**Phrase:** `Show at risk vendors`
```cypher
MATCH (v:Vendor)
WHERE v.risk_flag = true
RETURN v
ORDER BY v.risk_score DESC
LIMIT 25
```

**Phrase:** `Show vendor supply network`
```cypher
MATCH (v:Vendor)-[s:SUPPLIES]->(p:Product)
WHERE v.risk_flag = true
RETURN v, s, p
LIMIT 50
```

**Phrase:** `Show single source vendors`
```cypher
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WHERE p.single_source_risk = true
RETURN v, p
LIMIT 40
```

**Phrase:** `Show vendor alternatives`
```cypher
MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v_risk:Vendor)
WHERE v_risk.risk_flag = true
  AND a.is_actionable_alternative = true
RETURN v_alt, a, v_risk
LIMIT 30
```

---

### 5.2 — Inventory and Warehouse Phrases

**Phrase:** `Show stockout warehouses`
```cypher
MATCH (w:Warehouse)
WHERE w.stockout_sku_count > 0
RETURN w
ORDER BY w.stockout_sku_count DESC
```

**Phrase:** `Show stockout supply chain`
```cypher
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)<-[st:STOCKS]-(w:Warehouse)
WHERE st.stockout_flag = 1.0
RETURN v, p, st, w
LIMIT 40
```

**Phrase:** `Show bottleneck warehouses`
```cypher
MATCH (w:Warehouse)
WHERE w.is_bottleneck_warehouse = true
OPTIONAL MATCH (w)-[:SHIPS_TO]->(d:Destination)
RETURN w, d
LIMIT 30
```

**Phrase:** `Show warehouse capacity`
```cypher
MATCH (w:Warehouse)
WHERE w.capacity_status IN ['OVER_CAPACITY', 'HIGH_UTILIZATION']
RETURN w
ORDER BY w.utilization_pct DESC
```

**Phrase:** `Show below reorder products`
```cypher
MATCH (w:Warehouse)-[st:STOCKS]->(p:Product)
WHERE st.stock_on_hand < st.reorder_point
RETURN w, st, p
LIMIT 50
```

---

### 5.3 — Manufacturing and Plant Phrases

**Phrase:** `Show underperforming plants`
```cypher
MATCH (pl:Plant)
WHERE pl.performance_flag = true
RETURN pl
ORDER BY pl.performance_score DESC
```

**Phrase:** `Show plant production`
```cypher
MATCH (pl:Plant)-[r:PRODUCES]->(p:Product)
WHERE pl.performance_flag = true
RETURN pl, r, p
LIMIT 40
```

**Phrase:** `Show over capacity plants`
```cypher
MATCH (pl:Plant)
WHERE pl.utilization_status = 'OVER_CAPACITY'
RETURN pl
ORDER BY pl.avg_machine_utilization_pct DESC
```

**Phrase:** `Show high defect plants`
```cypher
MATCH (pl:Plant)
WHERE pl.avg_defect_rate_pct > 5.0
OPTIONAL MATCH (pl)-[:PRODUCES]->(p:Product)
RETURN pl, p
LIMIT 30
```

---

### 5.4 — Customer and Demand Phrases

**Phrase:** `Show VIP customers at risk`
```cypher
MATCH (c:Customer)
WHERE c.vip_at_risk_flag = true
RETURN c
ORDER BY c.total_revenue DESC
```

**Phrase:** `Show customer demand network`
```cypher
MATCH (c:Customer)-[d:DEMANDS]->(p:Product)
WHERE c.fulfillment_risk_flag = true
RETURN c, d, p
LIMIT 40
```

**Phrase:** `Show key accounts`
```cypher
MATCH (c:Customer)
WHERE c.revenue_tier = 'TIER_1_KEY_ACCOUNT'
RETURN c
ORDER BY c.total_revenue DESC
```

---

### 5.5 — Compounded Risk and Path Phrases

**Phrase:** `Show compounded risk products`
```cypher
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)
WHERE p.compounded_risk_flag = true
  AND v.risk_flag = true
RETURN v, p
LIMIT 30
```

**Phrase:** `Show full risk path`
```cypher
MATCH path =
  (v:Vendor)-[:SUPPLIES]->(p:Product)
  <-[:STOCKS]-(w:Warehouse)
  -[:SHIPS_TO]->(d:Destination)
  <-[:ORDERS_TO]-(c:Customer)
WHERE v.risk_flag = true
  AND p.single_source_risk = true
RETURN path
LIMIT 20
```

**Phrase:** `Show carrier risk routes`
```cypher
MATCH (ca:Carrier)-[hr:HANDLES_ROUTE]->(d:Destination)
WHERE ca.carrier_risk_flag = true
RETURN ca, hr, d
LIMIT 30
```

**Phrase:** `Show network hubs`
```cypher
MATCH (w:Warehouse)
WHERE w.hub_tier = 'MAJOR_HUB'
OPTIONAL MATCH (w)-[:SHIPS_TO]->(d:Destination)
RETURN w, d
LIMIT 40
```

---

## Section 6 — Create Five Named Scenes (Perspectives)

A Scene in Bloom is a saved canvas state — specific nodes loaded,
specific zoom level, specific layout. Create one scene per use case
so you can jump between views instantly during a demo.

> **How to save a Scene:**
> 1. Run a search phrase or load nodes manually
> 2. Arrange the layout (click **"Layouts"** → choose **Hierarchical**
>    or **Force-based**)
> 3. Click **"Save Scene"** (floppy disk icon top right)
> 4. Name it descriptively

---

### Scene 1: `Supply Risk Overview`

**Purpose:** The opening slide of any demo. Shows the entire at-risk
vendor and product landscape at a glance.

**Steps to create:**
1. Type `Show vendor supply network` in the search bar → Enter
2. Click **"Layouts"** → **"Force-based"** (spreads nodes naturally)
3. In the left panel → **"Filter"** → filter by `risk_flag = true`
4. Nodes should now show red/orange/green by your rules
5. Zoom out until you can see all nodes
6. Click **"Save Scene"** → name: `Supply Risk Overview`

**What it shows:**
- Red/orange Vendor nodes = at-risk suppliers
- Purple Product nodes sized by `vulnerability_score`
- Red SUPPLIES edges = under-delivery relationships
- Green Vendor nodes with green edges = healthy supply

---

### Scene 2: `Stockout Crisis Map`

**Purpose:** Shows the cascade from vendor → product → warehouse
for all active stockouts. Most impactful scene for urgency.

**Steps to create:**
1. Type `Show stockout supply chain` → Enter
2. Layout → **"Hierarchical"** → set direction **Top to Bottom**
3. This naturally flows: Vendor (top) → Product → Warehouse (bottom)
4. Save Scene → name: `Stockout Crisis Map`

**What it shows:**
- Vendors at top (orange = at-risk, red = critical)
- Products in middle (red = compounded risk, orange = stockout)
- Warehouses at bottom (red = stockout active)
- Flow of responsibility visible in the hierarchy

---

### Scene 3: `Manufacturing Performance`

**Purpose:** Plant health dashboard — who is over capacity, high defect
rate, or missing production targets.

**Steps to create:**
1. Type `Show plant production` → Enter
2. Layout → **"Hierarchical"** → Top to Bottom
3. Filter panel → add filter: `performance_flag = true`
4. Save Scene → name: `Manufacturing Performance`

**What it shows:**
- Plant nodes sized and coloured by `utilization_status`
- Red plants = over capacity or high defect rate
- PRODUCES edges connecting plants to their product lines
- Product nodes sized by `network_criticality`

---

### Scene 4: `Compounded Risk Deep Dive`

**Purpose:** The most powerful demo scene — shows the worst situation:
sole-vendor + high-risk vendor + stockout in one view.

**Steps to create:**
1. Type `Show full risk path` → Enter
2. Layout → **"Hierarchical"** → Left to Right
3. This renders the full chain: Vendor → Product → Warehouse →
   Destination → Customer
4. Save Scene → name: `Compounded Risk Deep Dive`

**What it shows:**
- Full supply chain path from source to customer in one view
- Every node coloured by its risk status
- RED path = the most dangerous supply chain scenario
- Click any node to expand its properties in the right panel

---

### Scene 5: `Vendor Rebalancing`

**Purpose:** Shows which vendors can substitute for at-risk ones.
Directly demonstrates the Recommendation Agent's graph intelligence.

**Steps to create:**
1. Type `Show vendor alternatives` → Enter
2. Layout → **"Force-based"**
3. ALTERNATIVE_FOR edges should appear in green (HIGH priority)
   or yellow (MEDIUM priority) per your relationship rules
4. Save Scene → name: `Vendor Rebalancing`

**What it shows:**
- At-risk Vendor nodes (red/orange)
- Potential alternative Vendors connected by ALTERNATIVE_FOR edges
- Green thick edges = HIGH priority actionable alternatives
- Click an ALTERNATIVE_FOR edge → see `cost_delta`,
  `lead_time_delta_days`, `shared_product_count` in the panel

---

## Section 7 — Use the Inspector Panel

When you click any node in Bloom, the **Inspector Panel** opens on
the right showing all properties. This is critical for demos —
stakeholders can see the exact risk data behind each visual.

### Key properties to highlight per entity type

**Vendor node — click to show:**
```
vendor_name           → who is this
reliability_tier      → CRITICAL / AT_RISK / GOOD / EXCELLENT
risk_score            → 0-100 (higher = more risky)
risk_reasons          → list explaining WHY they are risky
single_source_product_count → how many products depend solely on them
lifetime_spend        → financial exposure
```

**Product node — click to show:**
```
product_name          → what product
vulnerability_score   → 0-100
vulnerability_reasons → list of risk factors
supply_diversity      → SINGLE_SOURCE / LOW / WELL_DIVERSIFIED
network_criticality   → CRITICAL / HIGH / MEDIUM / LOW
total_revenue         → revenue at risk
```

**ALTERNATIVE_FOR edge — click to show:**
```
shared_product_count      → how many products overlap
cost_delta                → negative = alternative is cheaper
lead_time_delta_days      → positive = alternative is slower
recommendation_priority   → HIGH / MEDIUM / LOW
is_actionable_alternative → true/false
```

---

## Section 8 — Demo Flow (Walkthrough Script)

This is the recommended sequence for showing Bloom to stakeholders.
Takes approximately 10-15 minutes.

```
Step 1 — Open Scene: "Supply Risk Overview"
  Say: "This is our entire supply network. Red nodes are
        at-risk vendors. The size of each product node
        reflects how critical it is to the network."

Step 2 — Click a red Vendor node
  Say: "Clicking any vendor shows us exactly why it's flagged.
        See the risk_reasons list — this vendor has chronic
        under-delivery and low reliability. This is not
        LLM-generated — it's computed directly from the data."

Step 3 — Switch to Scene: "Stockout Crisis Map"
  Say: "This shows the cascade from vendor failures to
        warehouse stockouts. Top to bottom: vendor → product
        → warehouse. Every red connection is an active problem."

Step 4 — Switch to Scene: "Compounded Risk Deep Dive"
  Say: "This is the highest-risk scenario — a product that
        is single-sourced, whose only vendor is also at risk,
        and which is now in stockout. The full path from
        supplier to customer is visible in one view."

Step 5 — Switch to Scene: "Vendor Rebalancing"
  Say: "The graph has already computed which alternative
        vendors can substitute. Green edges are HIGH priority
        alternatives — cheaper and immediately actionable.
        Click any green edge to see the cost delta and
        lead time impact of the switch."

Step 6 — Type a custom search phrase
  Say: "Any team member can explore the graph using plain
        English. Let me show you..." 
        → Type: "Show VIP customers at risk"
  Say: "These are our key accounts with fulfillment rates
        below 85%. The graph connects their risk directly
        back to the vendors and warehouses causing it."
```

---

## Section 9 — Useful Cypher Queries to Run in Bloom

Bloom also has a **"Query"** mode where you can type raw Cypher.
Use these for ad-hoc investigation during a demo or analysis session.

### Expand a specific vendor's full neighbourhood

```cypher
// Replace 'Vendor Name Here' with an actual vendor name from your data
MATCH (v:Vendor {vendor_name: 'Vendor Name Here'})
OPTIONAL MATCH (v)-[:SUPPLIES]->(p:Product)
OPTIONAL MATCH (v)-[:ALTERNATIVE_FOR]->(v2:Vendor)
OPTIONAL MATCH (p)<-[:STOCKS]-(w:Warehouse)
RETURN v, p, w, v2
LIMIT 50
```

### Trace why a warehouse is in stockout

```cypher
// Replace warehouse name with your actual data
MATCH (w:Warehouse {warehouse_name: 'Warehouse Name Here'})
-[st:STOCKS]->(p:Product)
WHERE st.stockout_flag = 1.0
OPTIONAL MATCH (v:Vendor)-[:SUPPLIES]->(p)
OPTIONAL MATCH (pl:Plant)-[:PRODUCES]->(p)
RETURN w, st, p, v, pl
```

### Show the highest revenue at-risk path

```cypher
MATCH (c:Customer)-[d:DEMANDS]->(p:Product)
WHERE c.vip_at_risk_flag = true
OPTIONAL MATCH (v:Vendor)-[:SUPPLIES]->(p)
WHERE v.risk_flag = true
RETURN c, d, p, v
ORDER BY c.total_revenue DESC
LIMIT 20
```

### Show all CRITICAL nodes across entity types

```cypher
MATCH (n)
WHERE (n:Vendor AND n.reliability_tier = 'CRITICAL')
   OR (n:Product AND n.compounded_risk_flag = true)
   OR (n:Warehouse AND n.stockout_sku_count > 0)
   OR (n:Plant AND n.utilization_status = 'OVER_CAPACITY')
   OR (n:Customer AND n.vip_at_risk_flag = true)
RETURN n
LIMIT 50
```

---

## Section 10 — Verify Your Bloom Setup

```
✅ Bloom opens from Aura console without errors
✅ All 9 node labels visible in left panel
✅ Node display names show entity names (not UUIDs)
✅ Vendor nodes show red/orange/green based on reliability_tier rules
✅ All 20+ Search Phrases saved and working
✅ "Show critical vendors" returns red nodes
✅ "Show stockout supply chain" returns a 3-tier hierarchy
✅ "Show vendor alternatives" shows ALTERNATIVE_FOR edges
✅ Clicking a Vendor node shows risk_score and risk_reasons in panel
✅ All 5 Scenes saved and loadable
✅ Clicking an ALTERNATIVE_FOR edge shows cost_delta in inspector
```

If rules are not applying visually check:
- Property names are spelled exactly as in Step 3
  (e.g. `reliability_tier` not `reliabilityTier`)
- Values are the exact strings from Step 3
  (e.g. `CRITICAL` not `critical` — Neo4j is case-sensitive)
- The Perspective is active (selected in left panel)

---

## Summary: What You Have After Step 9

```
BLOOM SETUP:
  1 master Perspective  → "CPG Supply Chain"
  Node colours          → 7 entity types visually distinguished
  Style Rules           → 25+ rules mapping risk signals to visual cues
  Relationship Rules    → 7 rules on SUPPLIES, SHIPS_TO, ALTERNATIVE_FOR

SEARCH PHRASES (20):
  Vendor    → critical vendors, at risk, supply network,
               single source, alternatives
  Inventory → stockout warehouses, stockout supply chain,
               bottlenecks, capacity, below reorder
  Plant     → underperforming, production, over capacity, defects
  Customer  → VIP at risk, demand network, key accounts
  Risk      → compounded risk, full risk path, carrier routes, hubs

SAVED SCENES (5):
  Supply Risk Overview      → full at-risk vendor/product landscape
  Stockout Crisis Map       → vendor→product→warehouse cascade
  Manufacturing Performance → plant health by utilization/defect
  Compounded Risk Deep Dive → full chain: vendor→product→wh→dest→customer
  Vendor Rebalancing        → ALTERNATIVE_FOR alternatives visualised

DEMO CAPABILITY:
  10-15 min walkthrough script ready
  Any stakeholder can type plain English search phrases
  Click-through from visual anomaly to root property data
  No code, no Cypher knowledge required for end users
```
