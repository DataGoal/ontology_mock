# models/anomaly.py
# The canonical data structure for every anomaly this agent detects.
# Every downstream agent (Root Cause, Impact, Recommendation) receives
# one of these as input — so keep it consistent.

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class AnomalySignal(BaseModel):
    """
    A single detected anomaly from the knowledge graph.
    Immutable once created — downstream agents read but never modify it.
    """
    # Identity
    anomaly_id:         str            # e.g. "ANO-20250423-001"
    entity_type:        str            # Vendor / Product / Plant / Warehouse / Carrier / Customer
    entity_id:          str            # the node's primary key UUID
    entity_name:        str            # human-readable name for display

    # Classification
    anomaly_type:       str            # see ANOMALY_TYPE registry below
    severity:           str            # CRITICAL / HIGH / MEDIUM
    score:              int            # 0-100 composite, higher = worse

    # Explanation
    triggered_reasons:  List[str]      # list of human-readable reasons
    affected_products:  List[str]      # product names impacted (if applicable)
    affected_count:     int            # count of affected downstream entities

    # Metadata
    detected_at:        str            # ISO timestamp
    raw_data:           Dict[str, Any] # full node properties for downstream use

    # Optional enrichment added by downstream agents
    root_cause:         Optional[str]  = None
    impact_summary:     Optional[str]  = None
    recommendation:     Optional[str]  = None
    narrative:          Optional[str]  = None   # Claude-written summary


# ── Anomaly type registry ─────────────────────────────────────────────────────
# Every anomaly_type string this agent can emit, with its severity band
# and the entity type it applies to.

ANOMALY_TYPE_REGISTRY = {

    # Vendor anomalies
    "VENDOR_CRITICAL_RISK": {
        "entity_type": "Vendor",
        "severity":    "CRITICAL",
        "description": "Vendor risk_score >= 60 or reliability_tier = CRITICAL"
    },
    "VENDOR_HIGH_RISK": {
        "entity_type": "Vendor",
        "severity":    "HIGH",
        "description": "Vendor risk_score >= 30 or reliability_tier = AT_RISK"
    },
    "VENDOR_UNDER_DELIVERY": {
        "entity_type": "Vendor",
        "severity":    "HIGH",
        "description": "Vendor avg_delivery_variance_pct < -15 across products"
    },
    "VENDOR_SINGLE_SOURCE_CRITICAL": {
        "entity_type": "Vendor",
        "severity":    "CRITICAL",
        "description": "Vendor is sole supplier for 1+ products AND is high risk"
    },

    # Product anomalies
    "PRODUCT_COMPOUNDED_RISK": {
        "entity_type": "Product",
        "severity":    "CRITICAL",
        "description": "Single-source product whose only vendor is also high risk"
    },
    "PRODUCT_ACTIVE_STOCKOUT": {
        "entity_type": "Product",
        "severity":    "CRITICAL",
        "description": "Product has stockout_flag=1 in at least one warehouse"
    },
    "PRODUCT_LOW_FULFILLMENT": {
        "entity_type": "Product",
        "severity":    "HIGH",
        "description": "Product avg_fulfillment_rate < 85% across customers"
    },
    "PRODUCT_NO_VENDOR": {
        "entity_type": "Product",
        "severity":    "CRITICAL",
        "description": "Active product with zero vendor supply relationships"
    },

    # Plant anomalies
    "PLANT_OVER_CAPACITY": {
        "entity_type": "Plant",
        "severity":    "HIGH",
        "description": "Plant machine utilization > 90%"
    },
    "PLANT_HIGH_DEFECT_RATE": {
        "entity_type": "Plant",
        "severity":    "HIGH",
        "description": "Plant avg_defect_rate_pct > 5%"
    },
    "PLANT_EXCESSIVE_DOWNTIME": {
        "entity_type": "Plant",
        "severity":    "MEDIUM",
        "description": "Plant avg_downtime_hours > 4 per shift"
    },
    "PLANT_LOW_ATTAINMENT": {
        "entity_type": "Plant",
        "severity":    "MEDIUM",
        "description": "Plant production attainment < 80% of planned"
    },

    # Warehouse anomalies
    "WAREHOUSE_STOCKOUT": {
        "entity_type": "Warehouse",
        "severity":    "CRITICAL",
        "description": "Warehouse has 1+ SKUs in stockout"
    },
    "WAREHOUSE_OVER_CAPACITY": {
        "entity_type": "Warehouse",
        "severity":    "HIGH",
        "description": "Warehouse utilization > 95%"
    },
    "WAREHOUSE_BOTTLENECK": {
        "entity_type": "Warehouse",
        "severity":    "HIGH",
        "description": "Warehouse is sole stocking point for product(s) in stockout"
    },
    "WAREHOUSE_BELOW_REORDER": {
        "entity_type": "Warehouse",
        "severity":    "MEDIUM",
        "description": "1+ SKUs below reorder point — replenishment needed"
    },

    # Carrier anomalies
    "CARRIER_UNDERPERFORMING": {
        "entity_type": "Carrier",
        "severity":    "HIGH",
        "description": "Carrier on-time delivery < 75% across routes"
    },
    "CARRIER_HIGH_DELAY": {
        "entity_type": "Carrier",
        "severity":    "MEDIUM",
        "description": "Carrier avg_delay_days > 3 days across routes"
    },

    # Customer anomalies
    "CUSTOMER_VIP_AT_RISK": {
        "entity_type": "Customer",
        "severity":    "CRITICAL",
        "description": "High-value customer with fulfillment rate < 85%"
    },
    "CUSTOMER_LOW_FULFILLMENT": {
        "entity_type": "Customer",
        "severity":    "HIGH",
        "description": "Any customer with avg fulfillment rate < 70%"
    },
}