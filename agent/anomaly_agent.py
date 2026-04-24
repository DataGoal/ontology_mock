# agent/anomaly_agent.py
# Core anomaly detection logic.
# Runs all Cypher queries from the registry, converts results into
# AnomalySignal objects, and optionally adds Claude-written narratives.

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models.anomaly import AnomalySignal, ANOMALY_TYPE_REGISTRY
from agent.anomaly_queries import ANOMALY_QUERY_REGISTRY
from agent.prompts import ANOMALY_NARRATIVE_PROMPT

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


# ── Neo4j driver ──────────────────────────────────────────────────────────────

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ── LLM for narrative generation only ────────────────────────────────────────

def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=300       # narratives are short — cap tokens
    )


# ── Anomaly ID generator ──────────────────────────────────────────────────────

def generate_anomaly_id() -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_id = str(uuid.uuid4())[:6].upper()
    return f"ANO-{date_str}-{short_id}"


# ── Row → AnomalySignal converter ────────────────────────────────────────────

def row_to_signal(
    row: Dict,
    anomaly_type: str,
    entity_type: str,
    severity: str
) -> AnomalySignal:
    """
    Converts a single Cypher result row into an AnomalySignal object.
    All Cypher queries must return entity_id, entity_name, score,
    triggered_reasons, affected_products, affected_count.
    Everything else goes into raw_data for downstream agents.
    """
    # Extract guaranteed columns
    entity_id   = str(row.get("entity_id", "unknown"))
    entity_name = str(row.get("entity_name", "unknown"))
    score       = min(100, max(0, int(row.get("score", 0))))

    triggered_reasons = row.get("triggered_reasons", [])
    if isinstance(triggered_reasons, str):
        triggered_reasons = [triggered_reasons]

    affected_products = row.get("affected_products", [])
    if isinstance(affected_products, str):
        affected_products = [affected_products]
    # Filter out None values that Neo4j can return
    affected_products = [p for p in affected_products if p is not None]

    affected_count = int(row.get("affected_count", len(affected_products)))

    # Everything else is raw_data for downstream agents
    raw_data = {k: v for k, v in row.items()
                if k not in {"entity_id", "entity_name", "score",
                             "triggered_reasons", "affected_products",
                             "affected_count"}}

    return AnomalySignal(
        anomaly_id        = generate_anomaly_id(),
        entity_type       = entity_type,
        entity_id         = entity_id,
        entity_name       = entity_name,
        anomaly_type      = anomaly_type,
        severity          = severity,
        score             = score,
        triggered_reasons = triggered_reasons,
        affected_products = affected_products,
        affected_count    = affected_count,
        detected_at       = datetime.now(timezone.utc).isoformat(),
        raw_data          = raw_data
    )


# ── Single anomaly type detector ─────────────────────────────────────────────

def detect_anomaly_type(
    driver,
    anomaly_type: str,
    cypher: str
) -> List[AnomalySignal]:
    """
    Runs one Cypher query and returns all AnomalySignal objects found.
    """
    registry_entry = ANOMALY_TYPE_REGISTRY.get(anomaly_type, {})
    entity_type    = registry_entry.get("entity_type", "Unknown")
    severity       = registry_entry.get("severity", "MEDIUM")

    signals = []
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            results = session.run(cypher)
            for row in results:
                signal = row_to_signal(
                    dict(row),
                    anomaly_type,
                    entity_type,
                    severity
                )
                signals.append(signal)
    except Exception as e:
        print(f"  ⚠️  Query failed for {anomaly_type}: {e}")

    return signals


# ── Narrative generation ──────────────────────────────────────────────────────

def add_narrative(signal: AnomalySignal, llm) -> AnomalySignal:
    """
    Calls Claude to write a 2-3 sentence business narrative for one signal.
    Returns the signal with narrative field populated.
    """
    prompt = PromptTemplate(
        input_variables=[
            "entity_type", "entity_name", "anomaly_type",
            "severity", "score", "triggered_reasons", "affected_products"
        ],
        template=ANOMALY_NARRATIVE_PROMPT
    )
    chain = prompt | llm | StrOutputParser()

    try:
        narrative = chain.invoke({
            "entity_type":       signal.entity_type,
            "entity_name":       signal.entity_name,
            "anomaly_type":      signal.anomaly_type,
            "severity":          signal.severity,
            "score":             signal.score,
            "triggered_reasons": ", ".join(signal.triggered_reasons),
            "affected_products": ", ".join(signal.affected_products[:5])
                                  or "N/A"
        })
        # Return a new signal with narrative set (Pydantic models are immutable)
        return signal.model_copy(update={"narrative": narrative.strip()})
    except Exception as e:
        print(f"  ⚠️  Narrative generation failed for {signal.anomaly_id}: {e}")
        return signal


# ── Main detection run ────────────────────────────────────────────────────────

def run_anomaly_detection(
    anomaly_types:      Optional[List[str]] = None,
    severity_filter:    Optional[str]       = None,
    entity_type_filter: Optional[str]       = None,
    with_narratives:    bool                = True,
    max_signals:        int                 = 100
) -> Dict:
    """
    Runs the full anomaly detection sweep across the knowledge graph.

    Parameters:
      anomaly_types      : run only these types (default: all)
      severity_filter    : 'CRITICAL', 'HIGH', or 'MEDIUM' (default: all)
      entity_type_filter : 'Vendor', 'Product', 'Plant' etc (default: all)
      with_narratives    : call Claude to add narrative summaries (default: True)
      max_signals        : cap total signals returned (default: 100)

    Returns a dict with signals grouped by severity and summary stats.
    """
    print("\n" + "="*60)
    print("🔍 CPG Supply Chain — Anomaly Detection Run")
    print(f"   Started: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)

    # Determine which queries to run
    queries_to_run = {}
    for atype, cypher in ANOMALY_QUERY_REGISTRY.items():
        registry = ANOMALY_TYPE_REGISTRY.get(atype, {})

        # Apply filters
        if anomaly_types and atype not in anomaly_types:
            continue
        if severity_filter and registry.get("severity") != severity_filter:
            continue
        if entity_type_filter and registry.get("entity_type") != entity_type_filter:
            continue

        queries_to_run[atype] = cypher

    print(f"\n   Running {len(queries_to_run)} detection queries...\n")

    # Run all detection queries
    driver      = get_driver()
    all_signals = []

    try:
        for anomaly_type, cypher in queries_to_run.items():
            signals = detect_anomaly_type(driver, anomaly_type, cypher)
            if signals:
                print(f"  ✅ {anomaly_type}: {len(signals)} anomaly(ies) found")
            else:
                print(f"  ⬜ {anomaly_type}: none")
            all_signals.extend(signals)
    finally:
        driver.close()

    # Sort by severity then score — CRITICAL first
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    all_signals.sort(
        key=lambda s: (severity_order.get(s.severity, 9), -s.score)
    )

    # Cap results
    all_signals = all_signals[:max_signals]

    # Add Claude narratives if requested
    if with_narratives and all_signals:
        print(f"\n📝 Generating narratives for {len(all_signals)} signal(s)...")
        llm = get_llm()
        all_signals = [add_narrative(s, llm) for s in all_signals]

    # Build response summary
    critical = [s for s in all_signals if s.severity == "CRITICAL"]
    high     = [s for s in all_signals if s.severity == "HIGH"]
    medium   = [s for s in all_signals if s.severity == "MEDIUM"]

    summary = {
        "run_at":          datetime.now(timezone.utc).isoformat(),
        "total_anomalies": len(all_signals),
        "by_severity": {
            "CRITICAL": len(critical),
            "HIGH":     len(high),
            "MEDIUM":   len(medium),
        },
        "by_entity_type": {},
        "signals":         [s.model_dump() for s in all_signals],
        "critical_signals": [s.model_dump() for s in critical],
    }

    # Count by entity type
    for s in all_signals:
        summary["by_entity_type"][s.entity_type] = \
            summary["by_entity_type"].get(s.entity_type, 0) + 1

    print(f"\n{'='*60}")
    print(f"   Detection complete.")
    print(f"   CRITICAL: {len(critical)}  HIGH: {len(high)}  MEDIUM: {len(medium)}")
    print(f"   Total: {len(all_signals)} anomaly signal(s) emitted")
    print(f"{'='*60}\n")

    return summary