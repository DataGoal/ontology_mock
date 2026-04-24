# pipeline.py
# Orchestrates all 4 agents for one AnomalySignal end-to-end.
# Run directly: python pipeline.py
# Or call run_full_pipeline() from the API.

import json
from typing import List, Optional, Dict
from models.anomaly import AnomalySignal
from models.root_cause import RootCauseReport
from models.impact import ImpactReport
from models.recommendation import RecommendationSet
from agent.anomaly_agent import run_anomaly_detection
from agent.root_cause_agent import run_root_cause_analysis
from agent.impact_agent import run_impact_analysis
from agent.recommendation_agent import run_recommendation_agent


def run_full_pipeline(
    severity_filter:    Optional[str]  = "CRITICAL",
    with_narratives:    bool           = True,
    max_signals:        int            = 10
) -> List[Dict]:
    """
    Runs the complete 4-agent pipeline:
    Detect → Root Cause → Impact → Recommend

    Returns a list of fully enriched signal dicts.
    One dict per anomaly with all four agent outputs combined.
    """
    print("\n🚀 Starting Full Multi-Agent Pipeline")
    print(f"   Severity filter: {severity_filter or 'ALL'}")

    # ── Step 1: Anomaly Detection ─────────────────────────────────────────────
    print("\n[1/4] Running Anomaly Detection Agent...")
    detection_result = run_anomaly_detection(
        severity_filter = severity_filter,
        with_narratives = False,      # skip narrative here — done at end
        max_signals     = max_signals
    )

    signals = [
        AnomalySignal(**s)
        for s in detection_result["signals"]
    ]

    if not signals:
        print("   No anomalies detected. Pipeline complete.")
        return []

    print(f"   {len(signals)} anomaly(ies) detected.")

    # ── Steps 2-4: Per signal ─────────────────────────────────────────────────
    enriched_results = []

    for i, signal in enumerate(signals, 1):
        print(f"\n   Processing signal {i}/{len(signals)}: "
              f"[{signal.severity}] {signal.anomaly_type} — "
              f"{signal.entity_name}")

        # Step 2: Root Cause
        print(f"   [2/4] Root Cause Analysis...")
        root_cause = run_root_cause_analysis(
            signal, with_narrative=with_narratives
        )

        # Step 3: Impact Analysis
        print(f"   [3/4] Impact Analysis...")
        impact = run_impact_analysis(
            signal, with_narrative=with_narratives
        )

        # Step 4: Recommendation
        print(f"   [4/4] Recommendation...")
        recommendations = run_recommendation_agent(
            signal,
            root_cause     = root_cause,
            impact         = impact,
            with_narrative = with_narratives
        )

        enriched_results.append({
            "signal":          signal.model_dump(),
            "root_cause":      root_cause.model_dump(),
            "impact":          impact.model_dump(),
            "recommendations": recommendations.model_dump(),
        })

    print(f"\n✅ Pipeline complete. {len(enriched_results)} signal(s) enriched.")
    return enriched_results


if __name__ == "__main__":
    results = run_full_pipeline(
        severity_filter = "CRITICAL",
        with_narratives = True,
        max_signals     = 5
    )

    for r in results:
        sig  = r["signal"]
        rc   = r["root_cause"]
        imp  = r["impact"]
        rec  = r["recommendations"]

        print(f"\n{'='*65}")
        print(f"ANOMALY   : [{sig['severity']}] {sig['anomaly_type']}")
        print(f"ENTITY    : {sig['entity_name']}")
        print(f"SCORE     : {sig['score']}/100")
        print(f"\nROOT CAUSE: {rc.get('narrative', 'N/A')}")
        print(f"\nIMPACT    : Revenue at risk: "
              f"${imp['total_revenue_at_risk']:,.0f} | "
              f"Customers: {imp['customers_affected']} | "
              f"VIPs: {imp['vip_customers_affected']}")
        if imp.get("narrative"):
            print(f"           {imp['narrative']}")
        print(f"\nRECOMMENDATIONS ({rec['high_priority']} HIGH priority):")
        for rx in rec["recommendations"][:3]:
            print(f"  [{rx['priority']}] {rx['title']}")
        if rec.get("narrative"):
            print(f"\n  {rec['narrative']}")