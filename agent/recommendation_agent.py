# agent/recommendation_agent.py

import uuid
from typing import List, Dict, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agent.config import NEO4J_DATABASE, get_driver, get_llm
from models.anomaly import AnomalySignal
from models.root_cause import RootCauseReport
from models.impact import ImpactReport
from models.recommendation import Recommendation, RecommendationSet
from agent.prompts import RECOMMENDATION_PROMPT


def rec_id() -> str:
    return f"REC-{str(uuid.uuid4())[:8].upper()}"


# ── Graph queries for recommendation data ─────────────────────────────────────

def get_vendor_alternatives(driver, entity_id: str,
                            entity_type: str) -> List[Dict]:
    """
    Fetches ALTERNATIVE_FOR candidates for at-risk vendors.
    Used for SWITCH_VENDOR recommendations.
    """
    if entity_type == "Vendor":
        cypher = """
        MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v:Vendor {vendor_id: $entity_id})
        WHERE a.is_actionable_alternative = true
          AND v_alt.active = true
        RETURN v_alt.vendor_id          AS alt_vendor_id,
               v_alt.vendor_name        AS alt_vendor_name,
               v_alt.reliability_score  AS reliability_score,
               v_alt.reliability_tier   AS reliability_tier,
               v_alt.avg_lead_time_days AS lead_time_days,
               v_alt.tier               AS vendor_tier,
               v_alt.region             AS region,
               a.shared_product_count   AS shared_products,
               a.cost_delta             AS cost_delta,
               a.lead_time_delta_days   AS lead_time_delta,
               a.recommendation_priority AS priority,
               a.substitution_confidence AS confidence
        ORDER BY
            CASE a.recommendation_priority
                WHEN 'HIGH'   THEN 1
                WHEN 'MEDIUM' THEN 2
                ELSE 3
            END,
            v_alt.reliability_score DESC
        LIMIT 5
        """
    elif entity_type in ("Warehouse", "Product"):
        # Find vendors supplying the impacted products
        cypher = """
        MATCH (v_at_risk:Vendor)-[:SUPPLIES]->(p:Product)
        WHERE (p.product_id = $entity_id OR
               EXISTS {
                 MATCH (w:Warehouse {warehouse_id: $entity_id})-[:STOCKS]->(p)
               })
          AND v_at_risk.risk_flag = true
        WITH v_at_risk
        MATCH (v_alt:Vendor)-[a:ALTERNATIVE_FOR]->(v_at_risk)
        WHERE a.is_actionable_alternative = true
          AND v_alt.active = true
        RETURN v_alt.vendor_id          AS alt_vendor_id,
               v_alt.vendor_name        AS alt_vendor_name,
               v_alt.reliability_score  AS reliability_score,
               v_alt.reliability_tier   AS reliability_tier,
               v_alt.avg_lead_time_days AS lead_time_days,
               v_alt.tier               AS vendor_tier,
               v_alt.region             AS region,
               a.shared_product_count   AS shared_products,
               a.cost_delta             AS cost_delta,
               a.lead_time_delta_days   AS lead_time_delta,
               a.recommendation_priority AS priority,
               v_at_risk.vendor_name    AS replaces_vendor
        ORDER BY v_alt.reliability_score DESC
        LIMIT 5
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher, {"entity_id": entity_id})]


def get_rebalance_warehouses(driver, entity_id: str,
                             entity_type: str) -> List[Dict]:
    """
    Finds warehouses with overstock of the affected products
    that could transfer stock to address stockout.
    """
    if entity_type in ("Warehouse", "Product"):
        cypher = """
        MATCH (w_over:Warehouse)-[st:STOCKS]->(p:Product)
        WHERE st.overstock_flag = 1.0
          AND (
            p.product_id = $entity_id
            OR EXISTS {
              MATCH (w_out:Warehouse {warehouse_id: $entity_id})
                    -[:STOCKS]->(p)
            }
          )
        RETURN w_over.warehouse_id       AS warehouse_id,
               w_over.warehouse_name    AS warehouse_name,
               w_over.region            AS region,
               w_over.hub_tier          AS hub_tier,
               p.product_name           AS product_name,
               p.product_id             AS product_id,
               st.stock_on_hand         AS available_stock,
               st.safety_stock          AS safety_stock,
               (st.stock_on_hand - st.safety_stock * 1.5)
                                        AS transferable_units
        ORDER BY transferable_units DESC
        LIMIT 5
        """
        with driver.session(database=NEO4J_DATABASE) as session:
            return [dict(r) for r in session.run(cypher,
                                                 {"entity_id": entity_id})]
    return []


def get_alternative_carriers(driver, entity_id: str,
                             entity_type: str) -> List[Dict]:
    """
    Finds better-performing carriers on the same routes.
    Only relevant for Carrier anomalies.
    """
    if entity_type != "Carrier":
        return []

    cypher = """
    MATCH (ca_bad:Carrier {carrier_id: $entity_id})
          -[:HANDLES_ROUTE]->(d:Destination)
          <-[:HANDLES_ROUTE]-(ca_good:Carrier)
    WHERE ca_good.performance_tier IN ['PREMIUM', 'STANDARD']
      AND ca_good.active = true
      AND ca_good.carrier_id <> ca_bad.carrier_id
    RETURN ca_good.carrier_id           AS carrier_id,
           ca_good.carrier_name         AS carrier_name,
           ca_good.performance_tier     AS performance_tier,
           ca_good.network_on_time_pct  AS on_time_pct,
           ca_good.avg_transit_days     AS avg_transit_days,
           ca_good.carrier_type         AS carrier_type,
           collect(DISTINCT d.destination_name) AS shared_routes,
           count(DISTINCT d)            AS shared_route_count
    ORDER BY ca_good.network_on_time_pct DESC
    LIMIT 3
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher, {"entity_id": entity_id})]


# ── Recommendation builders ───────────────────────────────────────────────────

def build_vendor_switch_recommendations(
    alternatives: List[Dict],
    signal: AnomalySignal
) -> List[Recommendation]:
    recs = []
    for alt in alternatives:
        cost_delta = alt.get("cost_delta") or 0
        priority   = alt.get("priority") or "MEDIUM"
        confidence = 0.9 if priority == "HIGH" else \
                     0.7 if priority == "MEDIUM" else 0.5

        benefit = (
            f"Reliability improves to {alt.get('reliability_score', 0):.2f} "
            f"({alt.get('reliability_tier', 'N/A')}). "
            f"Cost {'savings' if cost_delta <= 0 else 'increase'}: "
            f"${abs(cost_delta):.2f}/unit."
        )

        recs.append(Recommendation(
            rec_id          = rec_id(),
            action_type     = "SWITCH_VENDOR",
            priority        = priority,
            confidence      = confidence,
            title           = f"Switch to {alt.get('alt_vendor_name', 'Alternative Vendor')}",
            description     = (
                f"Redirect procurement from {signal.entity_name} to "
                f"{alt.get('alt_vendor_name')}. "
                f"Covers {alt.get('shared_products', 0)} shared product(s). "
                f"Lead time delta: {alt.get('lead_time_delta', 0):+.1f} days."
            ),
            target_entity   = str(alt.get("alt_vendor_name", "")),
            expected_benefit = benefit,
            supporting_data  = alt
        ))
    return recs


def build_inventory_rebalance_recommendations(
    warehouses: List[Dict],
    signal: AnomalySignal
) -> List[Recommendation]:
    recs = []
    for wh in warehouses:
        transferable = wh.get("transferable_units") or 0
        if transferable <= 0:
            continue

        recs.append(Recommendation(
            rec_id          = rec_id(),
            action_type     = "REBALANCE_INVENTORY",
            priority        = "HIGH",
            confidence      = 0.85,
            title           = f"Transfer stock from {wh.get('warehouse_name')}",
            description     = (
                f"Transfer up to {transferable:,.0f} units of "
                f"{wh.get('product_name')} from "
                f"{wh.get('warehouse_name')} ({wh.get('region')}) "
                f"to address stockout at {signal.entity_name}."
            ),
            target_entity   = str(wh.get("warehouse_name", "")),
            expected_benefit = (
                f"Resolves stockout using existing network stock. "
                f"No new procurement needed."
            ),
            supporting_data  = wh
        ))
    return recs


def build_carrier_reroute_recommendations(
    carriers: List[Dict],
    signal: AnomalySignal
) -> List[Recommendation]:
    recs = []
    for ca in carriers:
        recs.append(Recommendation(
            rec_id          = rec_id(),
            action_type     = "REROUTE_SHIPMENT",
            priority        = "HIGH",
            confidence      = 0.80,
            title           = f"Reroute to {ca.get('carrier_name')}",
            description     = (
                f"Replace {signal.entity_name} with "
                f"{ca.get('carrier_name')} "
                f"({ca.get('performance_tier')}) on "
                f"{ca.get('shared_route_count', 0)} shared route(s). "
                f"On-time rate: {ca.get('on_time_pct', 0):.1f}%."
            ),
            target_entity   = str(ca.get("carrier_name", "")),
            expected_benefit = (
                f"On-time delivery improves from current level to "
                f"{ca.get('on_time_pct', 0):.1f}%."
            ),
            supporting_data  = ca
        ))
    return recs


def build_escalation_recommendation(
    signal: AnomalySignal,
    impact: Optional[ImpactReport]
) -> Recommendation:
    """
    Always added when severity=CRITICAL and no better option exists.
    """
    revenue = impact.total_revenue_at_risk if impact else 0
    return Recommendation(
        rec_id          = rec_id(),
        action_type     = "ESCALATE",
        priority        = "HIGH",
        confidence      = 1.0,
        title           = f"Escalate: {signal.entity_name} requires immediate attention",
        description     = (
            f"CRITICAL anomaly detected on {signal.entity_name}. "
            f"Estimated revenue at risk: ${revenue:,.0f}. "
            f"Escalate to supply chain leadership immediately."
        ),
        target_entity   = signal.entity_name,
        expected_benefit = "Ensures leadership visibility and rapid response.",
        supporting_data  = {"anomaly_score": signal.score,
                            "severity": signal.severity}
    )


# ── Narrative generation ──────────────────────────────────────────────────────

def generate_recommendation_narrative(
    signal:  AnomalySignal,
    report:  RecommendationSet,
    root_cause: Optional[RootCauseReport],
    impact:     Optional[ImpactReport],
    llm
) -> str:
    recs_text = "\n".join([
        f"  [{i+1}] [{r.priority}] {r.action_type}: {r.title}\n"
        f"       {r.description}"
        for i, r in enumerate(report.recommendations[:5])
    ])

    root_summary = (root_cause.narrative or "Root cause not yet determined"
                    if root_cause else "Root cause not yet determined")
    revenue      = impact.total_revenue_at_risk if impact else 0
    vip_count    = impact.vip_customers_affected if impact else 0

    prompt = PromptTemplate(
        input_variables=[
            "entity_name", "entity_type", "anomaly_type",
            "root_cause_summary", "revenue_at_risk",
            "vip_count", "recommendations_text"
        ],
        template=RECOMMENDATION_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({
            "entity_name":          signal.entity_name,
            "entity_type":          signal.entity_type,
            "anomaly_type":         signal.anomaly_type,
            "root_cause_summary":   root_summary[:300],
            "revenue_at_risk":      revenue,
            "vip_count":            vip_count,
            "recommendations_text": recs_text
        }).strip()
    except Exception as e:
        return f"Narrative generation failed: {e}"


# ── Main function ─────────────────────────────────────────────────────────────

def run_recommendation_agent(
    signal:         AnomalySignal,
    root_cause:     Optional[RootCauseReport] = None,
    impact:         Optional[ImpactReport]    = None,
    with_narrative: bool                      = True
) -> RecommendationSet:
    """
    Generates ranked recommendations for one AnomalySignal.
    Optionally uses RootCauseReport and ImpactReport for context.
    """
    driver = get_driver()
    all_recs: List[Recommendation] = []

    try:
        # Vendor switch options
        alternatives = get_vendor_alternatives(driver, signal.entity_id,
                                               signal.entity_type)
        all_recs += build_vendor_switch_recommendations(alternatives, signal)

        # Inventory rebalance options
        rebalance_whs = get_rebalance_warehouses(driver, signal.entity_id,
                                                 signal.entity_type)
        all_recs += build_inventory_rebalance_recommendations(rebalance_whs,
                                                              signal)

        # Carrier rerouting options
        alt_carriers = get_alternative_carriers(driver, signal.entity_id,
                                                signal.entity_type)
        all_recs += build_carrier_reroute_recommendations(alt_carriers, signal)

    finally:
        driver.close()

    # Always add escalation for CRITICAL signals
    if signal.severity == "CRITICAL":
        all_recs.append(build_escalation_recommendation(signal, impact))

    # Sort: HIGH priority first, then by confidence descending
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_recs.sort(
        key=lambda r: (priority_order.get(r.priority, 9), -r.confidence)
    )

    rec_set = RecommendationSet(
        anomaly_id    = signal.anomaly_id,
        entity_name   = signal.entity_name,
        anomaly_type  = signal.anomaly_type,
        total_recs    = len(all_recs),
        high_priority = sum(1 for r in all_recs if r.priority == "HIGH"),
        recommendations = all_recs
    )

    if with_narrative and all_recs:
        llm              = get_llm(max_tokens=500)
        rec_set.narrative = generate_recommendation_narrative(
            signal, rec_set, root_cause, impact, llm
        )

    return rec_set