# models/recommendation.py

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class Recommendation(BaseModel):
    """A single actionable recommendation."""
    rec_id:          str
    action_type:     str       # SWITCH_VENDOR / REBALANCE_INVENTORY /
                               # REROUTE_SHIPMENT / REDISTRIBUTE_PRODUCTION /
                               # EXPEDITE_ORDER / ESCALATE
    priority:        str       # HIGH / MEDIUM / LOW
    confidence:      float     # 0.0-1.0
    title:           str       # short action title
    description:     str       # what to do
    target_entity:   str       # who to act on
    expected_benefit: str      # what outcome to expect
    supporting_data: Dict[str, Any]  # raw graph data backing this rec


class RecommendationSet(BaseModel):
    """All recommendations for one AnomalySignal."""
    anomaly_id:       str
    entity_name:      str
    anomaly_type:     str
    total_recs:       int
    high_priority:    int
    recommendations:  List[Recommendation] = []
    narrative:        Optional[str]        = None