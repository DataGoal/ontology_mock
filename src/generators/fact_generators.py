"""
Fact Table Generators for CPG Supply Chain Data Model.

Each generator:
  1. Resolves FK pools from shared state (populated by dim generators).
  2. Applies domain-accurate distributions from config.
  3. Derives computed fields from business rules (e.g. total_cost = qty × unit_cost).
  4. Applies seasonality multipliers where configured.

Facts:
  FACT_PROCUREMENT, FACT_MANUFACTURING, FACT_INVENTORY,
  FACT_SHIPMENT, FACT_SALES_DEMAND
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.generators.base_generator import BaseGenerator
from utils.cpg_reference_data import PROCUREMENT_STATUSES, SHIPMENT_STATUSES


# ── Shared Helpers ─────────────────────────────────────────────────────────

def _seasonality_multiplier(rng, month_arr: np.ndarray, season_cfg: dict) -> np.ndarray:
    """Return a per-row demand multiplier based on calendar month."""
    multipliers = np.ones(len(month_arr))
    for idx, m in enumerate(month_arr):
        multipliers[idx] = float(season_cfg.get(str(m), 1.0))
    # Add small noise around the seasonal factor
    noise = rng.normal(1.0, 0.03, len(month_arr))
    return multipliers * noise


def _fk_months(date_df: pd.DataFrame, date_ids: np.ndarray) -> np.ndarray:
    """Map date_id array back to calendar month integers."""
    lookup = date_df.set_index("date_id")["month"].to_dict()
    return np.array([lookup.get(d, 6) for d in date_ids], dtype=int)


# ── FACT_PROCUREMENT ───────────────────────────────────────────────────────

class ProcurementFactGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("fact_procurement", {})
        rel  = self.config["relationships"]["foreign_key_strategies"]["fact_procurement"]
        season_cfg = self.config["distributions"].get("seasonality", {}).get("fact_procurement", {})
        active_cfg = self.config["relationships"].get("active_only_fks", {}).get("fact_procurement", [])

        # ── FK sampling ────────────────────────────────────────────────────
        vendor_ids    = self.sample_fk("dim_vendor",    "vendor_id",    n,
                                       strategy=rel["vendor_id"]["strategy"],
                                       pareto_factor=rel["vendor_id"].get("pareto_factor", 0.20),
                                       active_only="vendor_id" in active_cfg)
        product_ids   = self.sample_fk("dim_product",   "product_id",   n,
                                       strategy=rel["product_id"]["strategy"],
                                       pareto_factor=rel["product_id"].get("pareto_factor", 0.30),
                                       active_only="product_id" in active_cfg)
        date_ids      = self.sample_fk("dim_date",      "date_id",      n, strategy="uniform")
        warehouse_ids = self.sample_fk("dim_warehouse", "warehouse_id", n, strategy="uniform",
                                       active_only="warehouse_id" in active_cfg)

        # ── Seasonality ────────────────────────────────────────────────────
        months = _fk_months(self.state["dim_date"], date_ids)
        season = _seasonality_multiplier(self.rng, months, season_cfg)

        # ── Vendor lead time lookup ────────────────────────────────────────
        vendor_df = self.state["dim_vendor"].set_index("vendor_id")["avg_lead_time_days"].to_dict()
        vendor_lead = np.array([vendor_df.get(v, 21.0) for v in vendor_ids])

        # ── Quantities ────────────────────────────────────────────────────
        qty_cfg  = dist.get("quantity_ordered", {"mean": 10.0, "sigma": 1.2})
        qty_ordered = self.sample_lognormal(
            qty_cfg["mean"], qty_cfg["sigma"], n, low=100.0
        ) * season
        qty_ordered = np.clip(np.round(qty_ordered, 0), 100.0, 490000.0)

        fill_cfg = dist.get("fill_rate", {"alpha": 10.0, "beta": 1.0})
        fill_rate = self.sample_beta(fill_cfg["alpha"], fill_cfg["beta"], n, scale=1.0)
        fill_rate = np.clip(fill_rate, 0.70, 1.05)  # ±5% over/under
        qty_delivered = np.clip(np.round(qty_ordered * fill_rate, 0), 0.0, 490000.0)

        # ── Costs ─────────────────────────────────────────────────────────
        cost_cfg  = dist.get("unit_cost", {"mean": 1.5, "sigma": 1.0})
        unit_cost = self.sample_lognormal(cost_cfg["mean"], cost_cfg["sigma"], n, low=0.10, high=50.0)
        unit_cost = np.round(unit_cost, 4)
        total_cost = np.clip(np.round(qty_delivered * unit_cost, 2), 0.0, 4999999.0)

        # ── Delivery variance ─────────────────────────────────────────────
        delivery_variance_pct = np.clip(np.round(
            (qty_delivered - qty_ordered) / np.where(qty_ordered > 0, qty_ordered, 1) * 100, 4
        ), -29.9, 14.9)

        # ── Lead time (actual) ────────────────────────────────────────────
        lt_factor = self.rng.normal(1.05, 0.15, n)
        lead_time_days = np.clip(np.round(vendor_lead * lt_factor), 3, 120).astype(int)

        # ── Status ────────────────────────────────────────────────────────
        sw = dist.get("status_weights", {})
        statuses = self.sample_choice_dict(sw, n) if sw else \
                   self.sample_choice(PROCUREMENT_STATUSES, n)

        df = pd.DataFrame({
            "procurement_id":       self.uuids(n),
            "vendor_id":            vendor_ids,
            "product_id":           product_ids,
            "date_id":              date_ids,
            "warehouse_id":         warehouse_ids,
            "quantity_ordered":     qty_ordered,
            "quantity_delivered":   qty_delivered,
            "delivery_variance_pct": delivery_variance_pct,
            "unit_cost":            unit_cost,
            "total_cost":           total_cost,
            "lead_time_days":       lead_time_days,
            "status":               statuses,
        })

        self.state["fact_procurement"] = df
        self.logger.info(f"Generated fact_procurement: {len(df):,} rows")
        return df


# ── FACT_MANUFACTURING ─────────────────────────────────────────────────────

class ManufacturingFactGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("fact_manufacturing", {})
        rel  = self.config["relationships"]["foreign_key_strategies"]["fact_manufacturing"]
        active_cfg = self.config["relationships"].get("active_only_fks", {}).get("fact_manufacturing", [])

        # ── FK sampling ────────────────────────────────────────────────────
        plant_ids   = self.sample_fk("dim_plant",   "plant_id",   n,
                                     strategy=rel["plant_id"]["strategy"],
                                     pareto_factor=rel["plant_id"].get("pareto_factor", 0.25),
                                     active_only="plant_id" in active_cfg)
        product_ids = self.sample_fk("dim_product", "product_id", n,
                                     strategy=rel["product_id"]["strategy"],
                                     pareto_factor=rel["product_id"].get("pareto_factor", 0.25),
                                     active_only="product_id" in active_cfg)
        date_ids    = self.sample_fk("dim_date",    "date_id",    n, strategy="uniform")
        shift_ids   = self.sample_fk("dim_shift",   "shift_id",   n, strategy="uniform")

        # ── Plant capacity lookup (drives planned units) ───────────────────
        plant_df = self.state["dim_plant"].set_index("plant_id")["capacity_units_per_day"].to_dict()
        plant_cap = np.array([plant_df.get(p, 100000.0) for p in plant_ids])

        # Planned = fraction of daily capacity (5–95%)
        plan_fraction = self.rng.uniform(0.05, 0.95, n)
        units_planned = np.round(plant_cap * plan_fraction / 3.0, 0)  # ÷3 for per-shift
        units_planned = np.clip(units_planned, 500, None)

        # ── Attainment rate ────────────────────────────────────────────────
        att_cfg = dist.get("attainment_rate", {"alpha": 9.0, "beta": 1.5})
        attainment = self.sample_beta(att_cfg["alpha"], att_cfg["beta"], n, scale=1.0)
        attainment = np.clip(attainment, 0.50, 1.05)
        units_produced = np.round(units_planned * attainment, 0)

        # ── Quality ────────────────────────────────────────────────────────
        def_cfg = dist.get("defect_rate_pct", {"alpha": 1.5, "beta": 30.0})
        defect_rate = self.sample_beta(def_cfg["alpha"], def_cfg["beta"], n,
                                       scale=def_cfg.get("scale", 10.0))
        defect_rate = np.round(defect_rate, 4)

        # ── Throughput (units / 8 shift hours) ────────────────────────────
        throughput_rate = np.clip(np.round(units_produced / 8.0, 2), 0.0, 4999.0)

        # ── Machine utilisation ────────────────────────────────────────────
        util_cfg = dist.get("machine_utilization_pct", {"alpha": 7.0, "beta": 2.5})
        util_pct = self.sample_beta(util_cfg["alpha"], util_cfg["beta"], n,
                                    scale=util_cfg.get("scale", 100.0))
        util_pct = np.round(np.clip(util_pct, 30.0, 100.0), 2)

        # ── Downtime (inversely correlated with utilisation) ───────────────
        dt_cfg = dist.get("downtime_hours", {"mean": 0.3, "sigma": 0.8})
        downtime = self.sample_lognormal(dt_cfg["mean"], dt_cfg["sigma"], n, low=0.0, high=8.0)
        # If utilisation > 90%, constrain downtime to < 2 hrs
        downtime = np.where(util_pct > 90.0, np.clip(downtime, 0, 2.0), downtime)
        downtime = np.round(downtime, 2)

        df = pd.DataFrame({
            "manufacturing_id":        self.uuids(n),
            "plant_id":                plant_ids,
            "product_id":              product_ids,
            "date_id":                 date_ids,
            "shift_id":                shift_ids,
            "units_planned":           units_planned,
            "units_produced":          units_produced,
            "defect_rate_pct":         defect_rate,
            "throughput_rate":         throughput_rate,
            "machine_utilization_pct": util_pct,
            "downtime_hours":          downtime,
        })

        self.state["fact_manufacturing"] = df
        self.logger.info(f"Generated fact_manufacturing: {len(df):,} rows")
        return df


# ── FACT_INVENTORY ─────────────────────────────────────────────────────────

class InventoryFactGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("fact_inventory", {})
        active_cfg = self.config["relationships"].get("active_only_fks", {}).get("fact_inventory", [])

        # ── FK sampling ────────────────────────────────────────────────────
        warehouse_ids = self.sample_fk("dim_warehouse", "warehouse_id", n, strategy="uniform",
                                       active_only="warehouse_id" in active_cfg)
        product_ids   = self.sample_fk("dim_product",   "product_id",   n, strategy="uniform",
                                       active_only="product_id" in active_cfg)
        date_ids      = self.sample_fk("dim_date",       "date_id",     n, strategy="uniform")

        # ── Safety stock & reorder point ───────────────────────────────────
        # Base these on warehouse capacity and product weight
        wh_cap = self.state["dim_warehouse"].set_index("warehouse_id")["storage_capacity_units"].to_dict()
        base_capacity = np.array([wh_cap.get(w, 500000.0) for w in warehouse_ids])

        # Reorder point = 0.5–3% of warehouse capacity
        rop_fraction  = self.rng.uniform(0.005, 0.03, n)
        reorder_point = np.round(base_capacity * rop_fraction, 0)
        reorder_point = np.clip(reorder_point, 100, 50000)

        # Safety stock = 30–60% of reorder point
        ss_factor   = self.rng.uniform(0.30, 0.60, n)
        safety_stock = np.round(reorder_point * ss_factor, 0)
        safety_stock = np.clip(safety_stock, 50, 20000)

        # ── Stock on hand ──────────────────────────────────────────────────
        # Most days: healthy (1.5–5x safety stock), occasionally low or high
        dos_cfg = dist.get("days_of_supply_factor", {"mean": 1.5, "sigma": 0.6})
        dos_factor = self.sample_lognormal(dos_cfg["mean"], dos_cfg["sigma"], n, low=0.0)
        stock_on_hand = np.round(safety_stock * dos_factor, 0)
        stock_on_hand = np.clip(stock_on_hand, 0, None)

        # ── Flags ──────────────────────────────────────────────────────────
        stockout_p  = dist.get("stockout_probability",  0.04)
        overstock_p = dist.get("overstock_probability", 0.08)

        # Base flags on actual stock levels
        stockout_flag  = (stock_on_hand <= safety_stock).astype(float)
        overstock_flag = (stock_on_hand >= reorder_point * 3.0).astype(float)

        # Inject additional random stockout/overstock events
        stockout_rand  = self.rng.random(n) < stockout_p
        overstock_rand = self.rng.random(n) < overstock_p
        stockout_flag  = np.where(stockout_rand, 1.0, stockout_flag)
        # Ensure flags are mutually exclusive
        overstock_flag = np.where(stockout_flag == 1.0, 0.0,
                                  np.where(overstock_rand, 1.0, overstock_flag))

        df = pd.DataFrame({
            "inventory_id":  self.uuids(n),
            "warehouse_id":  warehouse_ids,
            "product_id":    product_ids,
            "date_id":       date_ids,
            "stock_on_hand": stock_on_hand,
            "reorder_point": reorder_point,
            "safety_stock":  safety_stock,
            "stockout_flag": stockout_flag,
            "overstock_flag": overstock_flag,
        })

        self.state["fact_inventory"] = df
        self.logger.info(f"Generated fact_inventory: {len(df):,} rows")
        return df


# ── FACT_SHIPMENT ──────────────────────────────────────────────────────────

class ShipmentFactGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("fact_shipment", {})
        rel  = self.config["relationships"]["foreign_key_strategies"]["fact_shipment"]
        active_cfg = self.config["relationships"].get("active_only_fks", {}).get("fact_shipment", [])

        # ── FK sampling ────────────────────────────────────────────────────
        carrier_ids   = self.sample_fk("dim_carrier",     "carrier_id",     n,
                                       strategy=rel["carrier_id"]["strategy"],
                                       pareto_factor=rel["carrier_id"].get("pareto_factor", 0.25),
                                       active_only="carrier_id" in active_cfg)
        product_ids   = self.sample_fk("dim_product",     "product_id",     n,
                                       strategy=rel["product_id"]["strategy"],
                                       pareto_factor=rel["product_id"].get("pareto_factor", 0.30),
                                       active_only="product_id" in active_cfg)
        date_ids      = self.sample_fk("dim_date",        "date_id",        n, strategy="uniform")
        warehouse_ids = self.sample_fk("dim_warehouse",   "warehouse_id",   n,
                                       strategy=rel["origin_warehouse_id"]["strategy"],
                                       pareto_factor=rel["origin_warehouse_id"].get("pareto_factor", 0.30),
                                       active_only="origin_warehouse_id" in active_cfg)
        dest_ids      = self.sample_fk("dim_destination", "destination_id", n,
                                       strategy=rel["destination_id"]["strategy"],
                                       pareto_factor=rel["destination_id"].get("pareto_factor", 0.20))

        # ── Carrier expected transit lookup ────────────────────────────────
        carrier_df = self.state["dim_carrier"].set_index("carrier_id")["avg_transit_days"].to_dict()
        transit_expected = np.array([carrier_df.get(c, 5.0) for c in carrier_ids])
        transit_expected = np.round(transit_expected, 1)

        # ── Actual transit with variance ───────────────────────────────────
        var_cfg = dist.get("transit_variance", {"mean": 0.8, "std": 2.5})
        variance = self.sample_normal(var_cfg["mean"], var_cfg["std"], n, low=-5.0, high=20.0)
        transit_actual = np.round(np.clip(transit_expected + variance, 1.0, 60.0), 1)
        delivery_variance_days = np.round(transit_actual - transit_expected, 1)

        # ── Quantities ─────────────────────────────────────────────────────
        qty_cfg = {"mean": 9.0, "sigma": 1.5}  # lognormal
        qty_shipped = np.round(
            self.sample_lognormal(qty_cfg["mean"], qty_cfg["sigma"], n, low=50.0, high=100000.0), 0
        )

        fill_cfg = dist.get("fill_rate", {"alpha": 12.0, "beta": 1.0})
        fill_rate = self.sample_beta(fill_cfg["alpha"], fill_cfg["beta"], n, scale=1.0)
        fill_rate = np.clip(fill_rate, 0.85, 1.0)
        qty_received = np.round(qty_shipped * fill_rate, 0)

        # ── Freight cost ───────────────────────────────────────────────────
        fpu_cfg = dist.get("freight_cost_per_unit", {"mean": 0.5, "sigma": 0.7})
        fpu = self.sample_lognormal(fpu_cfg["mean"], fpu_cfg["sigma"], n, low=0.01)
        freight_cost = np.round(qty_shipped * fpu, 2)
        freight_cost = np.clip(freight_cost, 50.0, 200000.0)

        # ── Status ─────────────────────────────────────────────────────────
        sw = dist.get("shipment_status_weights", {})
        statuses = self.sample_choice_dict(sw, n) if sw else \
                   self.sample_choice(SHIPMENT_STATUSES, n)

        df = pd.DataFrame({
            "shipment_id":            self.uuids(n),
            "carrier_id":             carrier_ids,
            "product_id":             product_ids,
            "date_id":                date_ids,
            "origin_warehouse_id":    warehouse_ids,
            "destination_id":         dest_ids,
            "quantity_shipped":       qty_shipped,
            "quantity_received":      qty_received,
            "transit_days_actual":    transit_actual,
            "transit_days_expected":  transit_expected,
            "delivery_variance_days": delivery_variance_days,
            "freight_cost":           freight_cost,
            "shipment_status":        statuses,
        })

        self.state["fact_shipment"] = df
        self.logger.info(f"Generated fact_shipment: {len(df):,} rows")
        return df


# ── FACT_SALES_DEMAND ──────────────────────────────────────────────────────

class SalesDemandFactGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("fact_sales_demand", {})
        rel  = self.config["relationships"]["foreign_key_strategies"]["fact_sales_demand"]
        season_cfg = self.config["distributions"].get("seasonality", {}).get("fact_sales_demand", {})
        active_cfg = self.config["relationships"].get("active_only_fks", {}).get("fact_sales_demand", [])

        # ── FK sampling ────────────────────────────────────────────────────
        product_ids  = self.sample_fk("dim_product",     "product_id",     n,
                                      strategy=rel["product_id"]["strategy"],
                                      pareto_factor=rel["product_id"].get("pareto_factor", 0.20),
                                      active_only="product_id" in active_cfg)
        customer_ids = self.sample_fk("dim_customer",    "customer_id",    n,
                                      strategy=rel["customer_id"]["strategy"],
                                      pareto_factor=rel["customer_id"].get("pareto_factor", 0.20),
                                      active_only="customer_id" in active_cfg)
        date_ids     = self.sample_fk("dim_date",        "date_id",        n, strategy="uniform")
        dest_ids     = self.sample_fk("dim_destination", "destination_id", n,
                                      strategy=rel["destination_id"]["strategy"],
                                      pareto_factor=rel["destination_id"].get("pareto_factor", 0.25))

        # ── Seasonality ────────────────────────────────────────────────────
        months = _fk_months(self.state["dim_date"], date_ids)
        season = _seasonality_multiplier(self.rng, months, season_cfg)

        # ── Demand volume ──────────────────────────────────────────────────
        dmnd_cfg = dist.get("demand_units", {"mean": 9.0, "sigma": 1.5})
        units_demanded = np.clip(np.round(
            self.sample_lognormal(dmnd_cfg["mean"], dmnd_cfg["sigma"], n, low=10.0) * season, 0
        ), 10.0, 499000.0)

        # ── Fulfillment ────────────────────────────────────────────────────
        ful_cfg = dist.get("fulfillment_rate_pct", {"alpha": 11.0, "beta": 1.2})
        fulfillment_rate_pct = self.sample_beta(ful_cfg["alpha"], ful_cfg["beta"], n,
                                                scale=ful_cfg.get("scale", 100.0))
        fulfillment_rate_pct = np.round(np.clip(fulfillment_rate_pct, 0.0, 100.0), 4)
        units_fulfilled = np.clip(np.round(units_demanded * fulfillment_rate_pct / 100.0, 0), 0.0, 499000.0)

        # ── Revenue ────────────────────────────────────────────────────────
        rpu_cfg = dist.get("revenue_per_unit", {"mean": 2.5, "sigma": 0.8})
        revenue_per_unit = self.sample_lognormal(rpu_cfg["mean"], rpu_cfg["sigma"], n, low=0.50)
        revenue = np.round(units_fulfilled * revenue_per_unit, 2)
        revenue = np.clip(revenue, 0.0, 20_000_000.0)

        df = pd.DataFrame({
            "demand_id":            self.uuids(n),
            "product_id":           product_ids,
            "customer_id":          customer_ids,
            "date_id":              date_ids,
            "destination_id":       dest_ids,
            "units_demanded":       units_demanded,
            "units_fulfilled":      units_fulfilled,
            "fulfillment_rate_pct": fulfillment_rate_pct,
            "revenue":              revenue,
        })

        self.state["fact_sales_demand"] = df
        self.logger.info(f"Generated fact_sales_demand: {len(df):,} rows")
        return df
