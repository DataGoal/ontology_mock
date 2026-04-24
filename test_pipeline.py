# test_pipeline.py

from pipeline import run_full_pipeline

print("── TEST 1: Full CRITICAL pipeline (no narratives — fast) ──")
results = run_full_pipeline(
    severity_filter = "CRITICAL",
    with_narratives = False,
    max_signals     = 5
)
print(f"Signals processed: {len(results)}")
for r in results[:2]:
    sig = r["signal"]
    rc  = r["root_cause"]
    imp = r["impact"]
    rec = r["recommendations"]
    print(f"\n  Signal    : {sig['anomaly_type']} — {sig['entity_name']}")
    print(f"  Root cause: {len(rc['contributing_causes'])} cause(s) found")
    print(f"  Primary   : {rc['primary_cause']['entity_name'] if rc['primary_cause'] else 'None'}")
    print(f"  Impact    : ${imp['total_revenue_at_risk']:,.0f} revenue at risk")
    print(f"  Recs      : {rec['total_recs']} total, {rec['high_priority']} HIGH")

print("\n── TEST 2: Single signal end-to-end with narratives ──")
results = run_full_pipeline(
    severity_filter = "CRITICAL",
    with_narratives = True,
    max_signals     = 1
)
if results:
    r   = results[0]
    rec = r["recommendations"]
    print(f"\n  Recommendation narrative:\n  {rec.get('narrative', 'None')}")