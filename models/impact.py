# models/impact.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ImpactedCustomer(BaseModel):
    customer_id:        str
    customer_name:      str
    revenue_at_risk:    float
    units_at_risk:      float
    fulfillment_rate:   float
    revenue_tier:       str
    is_vip:             bool
    affected_products:  List[str]


class ImpactedProduct(BaseModel):
    product_id:         str
    product_name:       str
    sku:                str
    total_stock:        float
    stockout_flag:      bool
    network_criticality: str
    affected_warehouses: List[str]


class ImpactReport(BaseModel):
    """
    Full downstream impact assessment for one AnomalySignal.
    """
    anomaly_id:             str
    entity_type:            str
    entity_name:            str
    anomaly_type:           str

    # Aggregated impact metrics
    total_revenue_at_risk:  float
    total_units_at_risk:    float
    customers_affected:     int
    products_affected:      int
    warehouses_affected:    int
    vip_customers_affected: int

    # Detailed breakdowns
    impacted_customers:     List[ImpactedCustomer] = []
    impacted_products:      List[ImpactedProduct]  = []

    # Narrative
    narrative:              Optional[str] = None