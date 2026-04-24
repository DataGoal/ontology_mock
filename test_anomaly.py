# test_anomaly.py — run from terminal: python test_anomaly.py

from agent.anomaly_agent import run_anomaly_detection

print("\n── TEST 1: Full detection, no narratives (fast) ──")
result = run_anomaly_detection(with_narratives=False)
print(f"Total signals: {result['total_anomalies']}")
print(f"By severity:   {result['by_severity']}")
print(f"By entity:     {result['by_entity_type']}")

print("\n── TEST 2: CRITICAL only, with narratives ──")
result = run_anomaly_detection(
    severity_filter = "CRITICAL",
    with_narratives = True,
    max_signals     = 10
)
for signal in result["critical_signals"][:3]:
    print(f"\n  [{signal['severity']}] {signal['anomaly_type']}")
    print(f"  Entity : {signal['entity_name']}")
    print(f"  Score  : {signal['score']}/100")
    print(f"  Reasons: {signal['triggered_reasons']}")
    print(f"  Affected: {signal['affected_products'][:3]}")
    if signal.get("narrative"):
        print(f"  Narrative: {signal['narrative']}")

print("\n── TEST 3: Vendor anomalies only ──")
result = run_anomaly_detection(
    entity_type_filter = "Vendor",
    with_narratives    = False
)
for s in result["signals"][:5]:
    print(f"  {s['severity']:<10} {s['anomaly_type']:<35} {s['entity_name']}")

print("\n── TEST 4: Specific anomaly types ──")
result = run_anomaly_detection(
    anomaly_types   = ["WAREHOUSE_STOCKOUT", "PRODUCT_ACTIVE_STOCKOUT",
                       "VENDOR_SINGLE_SOURCE_CRITICAL"],
    with_narratives = True,
    max_signals     = 20
)
print(f"Stockout/single-source signals: {result['total_anomalies']}")