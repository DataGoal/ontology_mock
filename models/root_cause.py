# models/root_cause.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class RootCauseNode(BaseModel):
    """
    A single node identified as a contributing root cause.
    Scored by its own enriched risk properties, not LLM opinion.
    """
    entity_type:    str            # Vendor / Plant / Carrier / Warehouse
    entity_id:      str
    entity_name:    str
    cause_type:     str            # e.g. VENDOR_UNDER_DELIVERY, PLANT_DOWNTIME
    weight:         float          # 0.0-1.0 — confidence this is the cause
    evidence:       List[str]      # specific properties that support this cause
    raw_properties: Dict[str, Any] # full node data for Claude context


class RootCauseReport(BaseModel):
    """
    Full root cause analysis result for one AnomalySignal.
    """
    anomaly_id:         str
    entity_type:        str
    entity_name:        str
    anomaly_type:       str
    primary_cause:      Optional[RootCauseNode] = None   # highest weighted cause
    contributing_causes: List[RootCauseNode]    = []     # all causes ranked
    traversal_depth:    int                              # hops explored upstream
    narrative:          Optional[str]           = None   # Claude explanation
    cypher_path:        Optional[str]           = None   # the path traversed