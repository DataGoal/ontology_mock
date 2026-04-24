# agent/root_cause_agent.py

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.anomaly import AnomalySignal
from models.root_cause import RootCauseNode, RootCauseReport
from agent.prompts import ROOT_CAUSE_PROMPT

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=400
    )


# ── Upstream traversal queries ────────────────────────────────────────────────
# Each query walks upstream from the anomaly's entity type.
# Returns nodes with their risk properties for scoring.

def get_upstream_vendors(driver, entity_id: str,
                         entity_type: str) -> List[Dict]:
    """
    Finds upstream Vendor nodes from any entity type.
    Path: Warehouse/Product → (STOCKS/SUPPLIES) → Vendor
    """
    if entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})
              -[:STOCKS]->(p:Product)
              <-[:SUPPLIES]-(v:Vendor)
        RETURN v.vendor_id          AS vendor_id,
               v.vendor_name        AS vendor_name,
               v.risk_flag          AS risk_flag,
               v.risk_score         AS risk_score,
               v.reliability_tier   AS reliability_tier,
               v.risk_reasons       AS risk_reasons,
               v.under_delivery_flag AS under_delivery_flag,
               v.overall_delivery_variance_pct AS delivery_variance,
               v.avg_lead_time_days AS avg_lead_time_days,
               v.single_source_product_count AS single_source_count,
               collect(DISTINCT p.product_name) AS products
        """
    elif entity_type == "Product":
        cypher = """
        MATCH (p:Product {product_id: $entity_id})
              <-[:SUPPLIES]-(v:Vendor)
        RETURN v.vendor_id          AS vendor_id,
               v.vendor_name        AS vendor_name,
               v.risk_flag          AS risk_flag,
               v.risk_score         AS risk_score,
               v.reliability_tier   AS reliability_tier,
               v.risk_reasons       AS risk_reasons,
               v.under_delivery_flag AS under_delivery_flag,
               v.overall_delivery_variance_pct AS delivery_variance,
               v.avg_lead_time_days AS avg_lead_time_days,
               v.single_source_product_count AS single_source_count,
               [p.product_name] AS products
        """
    elif entity_type == "Customer":
        cypher = """
        MATCH (c:Customer {customer_id: $entity_id})
              -[:DEMANDS]->(p:Product)
              <-[:SUPPLIES]-(v:Vendor)
        RETURN v.vendor_id          AS vendor_id,
               v.vendor_name        AS vendor_name,
               v.risk_flag          AS risk_flag,
               v.risk_score         AS risk_score,
               v.reliability_tier   AS reliability_tier,
               v.risk_reasons       AS risk_reasons,
               v.under_delivery_flag AS under_delivery_flag,
               v.overall_delivery_variance_pct AS delivery_variance,
               v.avg_lead_time_days AS avg_lead_time_days,
               v.single_source_product_count AS single_source_count,
               collect(DISTINCT p.product_name) AS products
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


def get_upstream_plants(driver, entity_id: str,
                        entity_type: str) -> List[Dict]:
    """
    Finds upstream Plant nodes from any entity type.
    Path: Warehouse/Product → (STOCKS/PRODUCES) → Plant
    """
    if entity_type == "Warehouse":
        cypher = """
        MATCH (w:Warehouse {warehouse_id: $entity_id})
              -[:STOCKS]->(p:Product)
              <-[:PRODUCES]-(pl:Plant)
        RETURN pl.plant_id                  AS plant_id,
               pl.plant_name               AS plant_name,
               pl.performance_flag         AS performance_flag,
               pl.performance_score        AS performance_score,
               pl.performance_issues       AS performance_issues,
               pl.utilization_status       AS utilization_status,
               pl.avg_machine_utilization_pct AS utilization_pct,
               pl.avg_defect_rate_pct      AS defect_rate_pct,
               pl.avg_downtime_hours       AS downtime_hours,
               pl.avg_production_attainment AS attainment_pct,
               collect(DISTINCT p.product_name) AS products
        """
    elif entity_type == "Product":
        cypher = """
        MATCH (p:Product {product_id: $entity_id})
              <-[:PRODUCES]-(pl:Plant)
        RETURN pl.plant_id                  AS plant_id,
               pl.plant_name               AS plant_name,
               pl.performance_flag         AS performance_flag,
               pl.performance_score        AS performance_score,
               pl.performance_issues       AS performance_issues,
               pl.utilization_status       AS utilization_status,
               pl.avg_machine_utilization_pct AS utilization_pct,
               pl.avg_defect_rate_pct      AS defect_rate_pct,
               pl.avg_downtime_hours       AS downtime_hours,
               pl.avg_production_attainment AS attainment_pct,
               [p.product_name] AS products
        """
    else:
        return []

    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


def get_upstream_carriers(driver, entity_id: str,
                          entity_type: str) -> List[Dict]:
    """
    Finds upstream Carrier nodes contributing to shipment issues.
    Only applies to Warehouse anomalies (outbound shipping context).
    """
    if entity_type != "Warehouse":
        return []

    cypher = """
    MATCH (w:Warehouse {warehouse_id: $entity_id})
          -[:SHIPS_TO]->(d:Destination)
          <-[:HANDLES_ROUTE]-(ca:Carrier)
    WHERE ca.carrier_risk_flag = true
    RETURN ca.carrier_id              AS carrier_id,
           ca.carrier_name            AS carrier_name,
           ca.performance_tier        AS performance_tier,
           ca.carrier_risk_flag       AS carrier_risk_flag,
           ca.network_on_time_pct     AS on_time_pct,
           ca.network_avg_delay_days  AS avg_delay_days,
           ca.coverage_tier           AS coverage_tier,
           collect(DISTINCT d.destination_name) AS destinations
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(cypher,
                                             {"entity_id": entity_id})]


# ── Weighted scoring logic ────────────────────────────────────────────────────

def score_vendor_cause(vendor: Dict) -> Optional[RootCauseNode]:
    """
    Scores a Vendor as a root cause candidate.
    Weight is computed from its enriched risk properties.
    """
    if not vendor.get("risk_flag"):
        return None

    weight   = 0.0
    evidence = []

    risk_score = vendor.get("risk_score") or 0
    weight += min(risk_score / 100.0 * 0.5, 0.5)   # up to 0.5 from risk score

    if vendor.get("under_delivery_flag"):
        weight   += 0.25
        variance  = vendor.get("delivery_variance") or 0
        evidence.append(
            f"under-delivery: {round(variance, 1)}% variance"
        )

    reliability = vendor.get("reliability_tier", "")
    if reliability == "CRITICAL":
        weight   += 0.20
        evidence.append("reliability_tier: CRITICAL")
    elif reliability == "AT_RISK":
        weight   += 0.10
        evidence.append("reliability_tier: AT_RISK")

    if (vendor.get("single_source_count") or 0) > 0:
        weight   += 0.10
        evidence.append(
            f"sole supplier for {vendor['single_source_count']} product(s)"
        )

    reasons = vendor.get("risk_reasons") or []
    evidence.extend(reasons[:3])

    return RootCauseNode(
        entity_type    = "Vendor",
        entity_id      = str(vendor.get("vendor_id", "")),
        entity_name    = str(vendor.get("vendor_name", "")),
        cause_type     = "VENDOR_SUPPLY_FAILURE",
        weight         = round(min(weight, 1.0), 3),
        evidence       = evidence,
        raw_properties = vendor
    )


def score_plant_cause(plant: Dict) -> Optional[RootCauseNode]:
    """
    Scores a Plant as a root cause candidate.
    """
    if not plant.get("performance_flag"):
        return None

    weight   = 0.0
    evidence = []

    perf_score = plant.get("performance_score") or 0
    weight += min(perf_score / 100.0 * 0.5, 0.5)

    defect_rate = plant.get("defect_rate_pct") or 0
    if defect_rate > 5.0:
        weight   += 0.20
        evidence.append(f"defect_rate: {round(defect_rate, 2)}%")

    downtime = plant.get("downtime_hours") or 0
    if downtime > 4.0:
        weight   += 0.15
        evidence.append(f"downtime: {round(downtime, 1)} hrs/shift")

    attainment = plant.get("attainment_pct") or 100
    if attainment < 80:
        weight   += 0.15
        evidence.append(f"attainment: {round(attainment, 1)}%")

    utilization = plant.get("utilization_status", "")
    if utilization == "OVER_CAPACITY":
        weight   += 0.10
        evidence.append("utilization_status: OVER_CAPACITY")

    issues = plant.get("performance_issues") or []
    evidence.extend(issues[:3])

    return RootCauseNode(
        entity_type    = "Plant",
        entity_id      = str(plant.get("plant_id", "")),
        entity_name    = str(plant.get("plant_name", "")),
        cause_type     = "PLANT_PRODUCTION_FAILURE",
        weight         = round(min(weight, 1.0), 3),
        evidence       = evidence,
        raw_properties = plant
    )


def score_carrier_cause(carrier: Dict) -> Optional[RootCauseNode]:
    """
    Scores a Carrier as a root cause candidate.
    """
    if not carrier.get("carrier_risk_flag"):
        return None

    weight   = 0.0
    evidence = []

    on_time = carrier.get("on_time_pct") or 100
    weight += max(0, (85 - on_time) / 85 * 0.5)
    evidence.append(f"on_time_pct: {round(on_time, 1)}%")

    delay = carrier.get("avg_delay_days") or 0
    if delay > 3.0:
        weight   += 0.30
        evidence.append(f"avg_delay: {round(delay, 1)} days")

    perf_tier = carrier.get("performance_tier", "")
    if perf_tier == "UNDERPERFORMING":
        weight   += 0.20
        evidence.append("performance_tier: UNDERPERFORMING")

    return RootCauseNode(
        entity_type    = "Carrier",
        entity_id      = str(carrier.get("carrier_id", "")),
        entity_name    = str(carrier.get("carrier_name", "")),
        cause_type     = "CARRIER_TRANSIT_FAILURE",
        weight         = round(min(weight, 1.0), 3),
        evidence       = evidence,
        raw_properties = carrier
    )


# ── Narrative generation ──────────────────────────────────────────────────────

def generate_root_cause_narrative(
    signal: AnomalySignal,
    causes: List[RootCauseNode],
    llm
) -> str:
    if not causes:
        return ("No upstream causes with sufficient risk signals found. "
                "The anomaly may be isolated or caused by external factors "
                "not captured in the current graph.")

    causes_text = "\n".join([
        f"  [{i+1}] {c.entity_type}: {c.entity_name} "
        f"(weight: {c.weight:.2f}) — {', '.join(c.evidence[:3])}"
        for i, c in enumerate(causes[:5])
    ])

    prompt = PromptTemplate(
        input_variables=["entity_name", "entity_type", "anomaly_type",
                         "severity", "triggered_reasons", "causes_text"],
        template=ROOT_CAUSE_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({
            "entity_name":       signal.entity_name,
            "entity_type":       signal.entity_type,
            "anomaly_type":      signal.anomaly_type,
            "severity":          signal.severity,
            "triggered_reasons": ", ".join(signal.triggered_reasons),
            "causes_text":       causes_text
        }).strip()
    except Exception as e:
        return f"Narrative generation failed: {e}"


# ── Main function ─────────────────────────────────────────────────────────────

def run_root_cause_analysis(
    signal: AnomalySignal,
    with_narrative: bool = True
) -> RootCauseReport:
    """
    Runs root cause analysis for one AnomalySignal.
    Traverses upstream, scores causes, optionally adds Claude narrative.
    """
    driver = get_driver()
    causes = []

    try:
        # Collect upstream candidates
        vendors  = get_upstream_vendors(driver, signal.entity_id,
                                        signal.entity_type)
        plants   = get_upstream_plants(driver, signal.entity_id,
                                       signal.entity_type)
        carriers = get_upstream_carriers(driver, signal.entity_id,
                                         signal.entity_type)

        # Score each candidate
        for v in vendors:
            node = score_vendor_cause(v)
            if node:
                causes.append(node)

        for pl in plants:
            node = score_plant_cause(pl)
            if node:
                causes.append(node)

        for ca in carriers:
            node = score_carrier_cause(ca)
            if node:
                causes.append(node)

    finally:
        driver.close()

    # Rank by weight descending
    causes.sort(key=lambda c: c.weight, reverse=True)

    # Generate narrative
    narrative = None
    if with_narrative:
        llm       = get_llm()
        narrative = generate_root_cause_narrative(signal, causes, llm)

    return RootCauseReport(
        anomaly_id          = signal.anomaly_id,
        entity_type         = signal.entity_type,
        entity_name         = signal.entity_name,
        anomaly_type        = signal.anomaly_type,
        primary_cause       = causes[0] if causes else None,
        contributing_causes = causes,
        traversal_depth     = 2,
        narrative           = narrative
    )