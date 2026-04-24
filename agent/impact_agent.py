# agent/impact_agent.py

from typing import List, Dict
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agent.config import NEO4J_DATABASE, get_driver, get_llm
from models.anomaly import AnomalySignal
from models.impact import ImpactReport, ImpactedCustomer, ImpactedProduct
from agent.prompts import IMPACT_ANALYSIS_PROMPT


# ── Downstream traversal queries ──────────────────────────────────────────────

def get_downstream_customers(driver, entity_id: str,
                              entity_type: str) -> List[Dict]:
    """
    Finds all downstream Customers affected by the anomaly.
    Path depends on entity type — all paths eventually reach Customer.
    """
    if entity_type == "Vendor":
        cypher = """
        MATCH (v:Vendor {vendor_id: $entity_id})
              -[:SUPPLIES]->(p:Product)
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Product":
        cypher = """
        MATCH (p:Product {product_id: $entity_id})
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               [p.product_name]         AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})
              -[:STOCKS]->(p:Product)
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Plant":
        cypher = """
        MATCH (pl:Plant {plant_id: $entity_id})
              -[:PRODUCES]->(p:Product)
              <-[d:DEMANDS]-(c:Customer)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    elif entity_type == "Carrier":
        cypher = """
        MATCH (ca:Carrier {carrier_id: $entity_id})
              -[:HANDLES_ROUTE]->(d_dest:Destination)
              <-[:ORDERS_TO]-(c:Customer)
        OPTIONAL MATCH (c)-[d:DEMANDS]->(p:Product)
        RETURN c.customer_id             AS customer_id,
               c.customer_name          AS customer_name,
               c.revenue_tier           AS revenue_tier,
               c.vip_at_risk_flag       AS is_vip,
               c.avg_fulfillment_rate   AS fulfillment_rate,
               sum(d.total_revenue)     AS revenue_at_risk,
               sum(d.total_units_demanded) AS units_at_risk,
               collect(DISTINCT p.product_name) AS affected_products
        ORDER BY revenue_at_risk DESC
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


def get_downstream_products(driver, entity_id: str,
                             entity_type: str) -> List[Dict]:
    """
    Finds all downstream Products affected.
    """
    if entity_type == "Vendor":
        cypher = """
        MATCH (v:Vendor {vendor_id: $entity_id})-[:SUPPLIES]->(p:Product)
        OPTIONAL MATCH (w:Warehouse)-[st:STOCKS]->(p)
        RETURN p.product_id              AS product_id,
               p.product_name           AS product_name,
               p.sku                    AS sku,
               p.network_criticality    AS network_criticality,
               p.has_any_stockout       AS stockout_flag,
               sum(coalesce(st.stock_on_hand, 0)) AS total_stock,
               collect(DISTINCT w.warehouse_name) AS affected_warehouses
        """
    elif entity_type == "Plant":
        cypher = """
        MATCH (pl:Plant {plant_id: $entity_id})-[:PRODUCES]->(p:Product)
        OPTIONAL MATCH (w:Warehouse)-[st:STOCKS]->(p)
        RETURN p.product_id              AS product_id,
               p.product_name           AS product_name,
               p.sku                    AS sku,
               p.network_criticality    AS network_criticality,
               p.has_any_stockout       AS stockout_flag,
               sum(coalesce(st.stock_on_hand, 0)) AS total_stock,
               collect(DISTINCT w.warehouse_name) AS affected_warehouses
        """
    elif entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})-[st:STOCKS]->(p:Product)
        WHERE st.stockout_flag = 1.0 OR st.stock_on_hand < st.reorder_point
        RETURN p.product_id              AS product_id,
               p.product_name           AS product_name,
               p.sku                    AS sku,
               p.network_criticality    AS network_criticality,
               (st.stockout_flag = 1.0) AS stockout_flag,
               st.stock_on_hand         AS total_stock,
               [w.warehouse_name]       AS affected_warehouses
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


# ── Build report ──────────────────────────────────────────────────────────────

def build_impact_report(signal: AnomalySignal,
                        customers: List[Dict],
                        products: List[Dict]) -> ImpactReport:
    impacted_customers = [
        ImpactedCustomer(
            customer_id       = str(c.get("customer_id", "")),
            customer_name     = str(c.get("customer_name", "")),
            revenue_at_risk   = float(c.get("revenue_at_risk") or 0),
            units_at_risk     = float(c.get("units_at_risk") or 0),
            fulfillment_rate  = float(c.get("fulfillment_rate") or 0),
            revenue_tier      = str(c.get("revenue_tier") or ""),
            is_vip            = bool(c.get("is_vip") or False),
            affected_products = [p for p in (c.get("affected_products") or [])
                                 if p is not None]
        )
        for c in customers
    ]

    impacted_products = [
        ImpactedProduct(
            product_id          = str(p.get("product_id", "")),
            product_name        = str(p.get("product_name", "")),
            sku                 = str(p.get("sku") or ""),
            total_stock         = float(p.get("total_stock") or 0),
            stockout_flag       = bool(p.get("stockout_flag") or False),
            network_criticality = str(p.get("network_criticality") or ""),
            affected_warehouses = [w for w in
                                   (p.get("affected_warehouses") or [])
                                   if w is not None]
        )
        for p in products
    ]

    return ImpactReport(
        anomaly_id             = signal.anomaly_id,
        entity_type            = signal.entity_type,
        entity_name            = signal.entity_name,
        anomaly_type           = signal.anomaly_type,
        total_revenue_at_risk  = sum(c.revenue_at_risk
                                     for c in impacted_customers),
        total_units_at_risk    = sum(c.units_at_risk
                                     for c in impacted_customers),
        customers_affected     = len(impacted_customers),
        products_affected      = len(impacted_products),
        warehouses_affected    = len({
            w for p in impacted_products
            for w in p.affected_warehouses
        }),
        vip_customers_affected = sum(1 for c in impacted_customers
                                     if c.is_vip),
        impacted_customers     = impacted_customers,
        impacted_products      = impacted_products,
    )


def generate_impact_narrative(report: ImpactReport, llm) -> str:
    customers_text = "\n".join([
        f"  • {c.customer_name} ({c.revenue_tier}): "
        f"${c.revenue_at_risk:,.0f} at risk"
        f"{'  ⚠️ VIP' if c.is_vip else ''}"
        for c in report.impacted_customers[:5]
    ]) or "  No direct customer data found"

    products_text = "\n".join([
        f"  • {p.product_name} [{p.network_criticality}]"
        f"{'  🔴 STOCKOUT' if p.stockout_flag else ''}"
        for p in report.impacted_products[:5]
    ]) or "  No direct product data found"

    prompt = PromptTemplate(
        input_variables=[
            "entity_name", "entity_type", "anomaly_type", "severity",
            "total_revenue_at_risk", "total_units_at_risk",
            "customers_affected", "vip_customers_affected",
            "products_affected", "warehouses_affected",
            "customers_text", "products_text"
        ],
        template=IMPACT_ANALYSIS_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({
            "entity_name":           report.entity_name,
            "entity_type":           report.entity_type,
            "anomaly_type":          report.anomaly_type,
            "severity":              "HIGH",
            "total_revenue_at_risk": report.total_revenue_at_risk,
            "total_units_at_risk":   report.total_units_at_risk,
            "customers_affected":    report.customers_affected,
            "vip_customers_affected": report.vip_customers_affected,
            "products_affected":     report.products_affected,
            "warehouses_affected":   report.warehouses_affected,
            "customers_text":        customers_text,
            "products_text":         products_text,
        }).strip()
    except Exception as e:
        return f"Narrative generation failed: {e}"


# ── Main function ─────────────────────────────────────────────────────────────

def run_impact_analysis(
    signal: AnomalySignal,
    with_narrative: bool = True
) -> ImpactReport:
    """
    Runs downstream impact analysis for one AnomalySignal.
    """
    driver    = get_driver()
    customers = []
    products  = []

    try:
        customers = get_downstream_customers(driver, signal.entity_id,
                                             signal.entity_type)
        products  = get_downstream_products(driver, signal.entity_id,
                                            signal.entity_type)
    finally:
        driver.close()

    report = build_impact_report(signal, customers, products)

    if with_narrative:
        llm              = get_llm(max_tokens=400)
        report.narrative = generate_impact_narrative(report, llm)

    return report