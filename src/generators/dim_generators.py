"""
Dimension Table Generators for CPG Supply Chain Data Model.
Each generator produces realistic, domain-accurate dimension data.

Dimensions:
  - DIM_DATE, DIM_VENDOR, DIM_PLANT, DIM_SHIFT, DIM_WAREHOUSE,
    DIM_CARRIER, DIM_PRODUCT, DIM_CUSTOMER, DIM_DESTINATION
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from src.generators.base_generator import BaseGenerator
from utils.cpg_reference_data import (
    CPG_PRODUCT_CATALOG, VENDOR_DATA, PLANT_DATA, WAREHOUSE_DATA,
    CARRIER_DATA, CUSTOMER_SEGMENTS, CUSTOMER_CHANNELS, DESTINATION_DATA,
    SHIFT_DATA, VENDOR_TIERS, PACKAGING_TYPES, SUPERVISOR_NAMES,
    COUNTRY_REGION_MAP,
)


# ── DIM_DATE ───────────────────────────────────────────────────────────────

class DateDimGenerator(BaseGenerator):
    """Generate a complete calendar date dimension for a given date range."""

    # US Federal holidays (month, day) – fixed dates
    _FIXED_HOLIDAYS = {(1, 1), (7, 4), (11, 11), (12, 25), (12, 26)}

    def _is_holiday(self, d: date) -> bool:
        """Approximate US federal holiday check."""
        if (d.month, d.day) in self._FIXED_HOLIDAYS:
            return True
        # Thanksgiving: 4th Thursday in November
        if d.month == 11 and d.weekday() == 3:
            thursdays = [(date(d.year, 11, day)) for day in range(1, 31)
                         if date(d.year, 11, day).weekday() == 3]
            if len(thursdays) >= 4 and d == thursdays[3]:
                return True
        # Labor Day: 1st Monday in September
        if d.month == 9 and d.weekday() == 0:
            mondays = [date(d.year, 9, day) for day in range(1, 8)
                       if date(d.year, 9, day).weekday() == 0]
            if mondays and d == mondays[0]:
                return True
        # Memorial Day: last Monday in May
        if d.month == 5 and d.weekday() == 0:
            all_mondays = [date(d.year, 5, day) for day in range(1, 32)
                           if date(d.year, 5, day).weekday() == 0]
            if all_mondays and d == all_mondays[-1]:
                return True
        return False

    def generate(self, n: int = None, start: str = None, end: str = None) -> pd.DataFrame:
        """
        n is ignored here; dates are generated from start/end date range.
        If start/end not provided, falls back to config.
        """
        vol_cfg = self.config["volumes"]
        active  = vol_cfg["active_profile"]
        profile = vol_cfg["profiles"][active]
        s = start or profile["date_range"]["start"]
        e = end   or profile["date_range"]["end"]

        start_dt = date.fromisoformat(s)
        end_dt   = date.fromisoformat(e)
        delta    = (end_dt - start_dt).days + 1

        rows = []
        for i in range(delta):
            d = start_dt + timedelta(days=i)
            rows.append({
                "date_id":     str(self.uuids(1)[0]),
                "full_date":   d.isoformat(),
                "year":        d.year,
                "quarter":     (d.month - 1) // 3 + 1,
                "month":       d.month,
                "week":        d.isocalendar()[1],
                "month_name":  d.strftime("%B"),
                "day_of_week": d.strftime("%A"),
                "is_weekend":  d.weekday() >= 5,
                "is_holiday":  self._is_holiday(d),
            })

        df = pd.DataFrame(rows)
        self.state["dim_date"] = df
        self.logger.info(f"Generated dim_date: {len(df):,} rows ({s} → {e})")
        return df


# ── DIM_VENDOR ─────────────────────────────────────────────────────────────

class VendorDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("dim_vendor", {})
        active_ratio = dist.get("active_ratio", 0.88)
        tier_weights = dist.get("tier_weights", {"Tier 1": 0.25, "Tier 2": 0.45, "Tier 3": 0.30})

        # Draw from reference data; if n > catalog, cycle with variations
        pool = VENDOR_DATA * (n // len(VENDOR_DATA) + 1)
        selected = pool[:n]

        ids = self.uuids(n)

        reliability_scores = self.sample_beta(
            dist.get("reliability_score", {}).get("alpha", 8.0),
            dist.get("reliability_score", {}).get("beta", 2.0),
            n
        )
        lead_times = self.sample_lognormal(
            dist.get("avg_lead_time_days", {}).get("mean", 3.2),
            dist.get("avg_lead_time_days", {}).get("sigma", 0.5),
            n, low=5.0, high=90.0
        )
        tiers   = self.sample_choice_dict(tier_weights, n)
        actives = self.sample_bools(active_ratio, n)

        rows = []
        for i, v in enumerate(selected):
            suffix = f" #{i+1}" if i >= len(VENDOR_DATA) else ""
            rows.append({
                "vendor_id":          ids[i],
                "vendor_name":        v["name"] + suffix,
                "vendor_type":        v["type"],
                "country":            v["country"],
                "region":             v["region"],
                "tier":               tiers[i],
                "reliability_score":  round(float(reliability_scores[i]), 4),
                "avg_lead_time_days": round(float(lead_times[i]), 2),
                "active":             bool(actives[i]),
            })

        df = pd.DataFrame(rows)
        self.state["dim_vendor"] = df
        self.logger.info(f"Generated dim_vendor: {len(df):,} rows")
        return df


# ── DIM_PLANT ──────────────────────────────────────────────────────────────

class PlantDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("dim_plant", {})
        active_ratio = dist.get("active_ratio", 0.90)

        pool     = PLANT_DATA * (n // len(PLANT_DATA) + 1)
        selected = pool[:n]
        ids      = self.uuids(n)
        actives  = self.sample_bools(active_ratio, n)

        rows = []
        for i, p in enumerate(selected):
            suffix = f"-{i:02d}" if i >= len(PLANT_DATA) else ""
            rows.append({
                "plant_id":               ids[i],
                "plant_name":             p["name"] + suffix,
                "plant_code":             p["code"] + (f"{i:02d}" if i >= len(PLANT_DATA) else ""),
                "country":                p["country"],
                "region":                 COUNTRY_REGION_MAP.get(p["country"], "North America"),
                "capacity_units_per_day": float(p["capacity"]) * self.rng.uniform(0.85, 1.15),
                "plant_type":             p["type"],
                "active":                 bool(actives[i]),
            })

        df = pd.DataFrame(rows)
        # Ensure plant_code uniqueness
        df["plant_code"] = df["plant_code"] + df.groupby("plant_code").cumcount().apply(
            lambda x: f"-V{x}" if x > 0 else ""
        )
        self.state["dim_plant"] = df
        self.logger.info(f"Generated dim_plant: {len(df):,} rows")
        return df


# ── DIM_SHIFT ──────────────────────────────────────────────────────────────

class ShiftDimGenerator(BaseGenerator):

    def generate(self, n: int = 3) -> pd.DataFrame:
        """Always generates exactly 3 standard shifts."""
        ids        = self.uuids(3)
        supervisors = self.rng.choice(SUPERVISOR_NAMES, size=3, replace=False)

        rows = []
        for i, s in enumerate(SHIFT_DATA):
            base = datetime(2024, 1, 1)
            start_h, start_m, _ = [int(x) for x in s["start"].split(":")]
            end_h,   end_m,   _ = [int(x) for x in s["end"].split(":")]
            shift_start = datetime(2024, 1, 1, start_h, start_m, 0)
            # Night shift ends next day
            if end_h < start_h:
                shift_end = datetime(2024, 1, 2, end_h, end_m, 0)
            else:
                shift_end = datetime(2024, 1, 1, end_h, end_m, 0)
            rows.append({
                "shift_id":         ids[i],
                "shift_name":       s["name"],
                "shift_start":      shift_start.strftime("%Y-%m-%d %H:%M:%S"),
                "shift_end":        shift_end.strftime("%Y-%m-%d %H:%M:%S"),
                "shift_supervisor": supervisors[i],
            })

        df = pd.DataFrame(rows)
        self.state["dim_shift"] = df
        self.logger.info(f"Generated dim_shift: {len(df):,} rows")
        return df


# ── DIM_WAREHOUSE ──────────────────────────────────────────────────────────

class WarehouseDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("dim_warehouse", {})
        active_ratio = dist.get("active_ratio", 0.92)

        pool     = WAREHOUSE_DATA * (n // len(WAREHOUSE_DATA) + 1)
        selected = pool[:n]
        ids      = self.uuids(n)
        actives  = self.sample_bools(active_ratio, n)

        rows = []
        for i, w in enumerate(selected):
            suffix = f"-{i:02d}" if i >= len(WAREHOUSE_DATA) else ""
            rows.append({
                "warehouse_id":           ids[i],
                "warehouse_name":         w["name"] + suffix,
                "warehouse_code":         w["code"] + (f"{i:02d}" if i >= len(WAREHOUSE_DATA) else ""),
                "type":                   w["type"],
                "country":                w["country"],
                "region":                 COUNTRY_REGION_MAP.get(w["country"], "North America"),
                "storage_capacity_units": float(w["capacity"]) * self.rng.uniform(0.90, 1.10),
                "active":                 bool(actives[i]),
            })

        df = pd.DataFrame(rows)
        df["warehouse_code"] = df["warehouse_code"] + df.groupby("warehouse_code").cumcount().apply(
            lambda x: f"-V{x}" if x > 0 else ""
        )
        self.state["dim_warehouse"] = df
        self.logger.info(f"Generated dim_warehouse: {len(df):,} rows")
        return df


# ── DIM_CARRIER ────────────────────────────────────────────────────────────

class CarrierDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("dim_carrier", {})
        active_ratio = dist.get("active_ratio", 0.85)

        pool     = CARRIER_DATA * (n // len(CARRIER_DATA) + 1)
        selected = pool[:n]
        ids      = self.uuids(n)
        actives  = self.sample_bools(active_ratio, n)

        rows = []
        for i, c in enumerate(selected):
            suffix = f" #{i+1}" if i >= len(CARRIER_DATA) else ""
            # Add small noise to reference values for variety
            transit_jitter = self.rng.normal(1.0, 0.05)
            otd_jitter     = self.rng.normal(1.0, 0.03)
            rows.append({
                "carrier_id":           ids[i],
                "carrier_name":         c["name"] + suffix,
                "carrier_type":         c["type"],
                "country":              c["country"],
                "avg_transit_days":     round(c["avg_transit"] * max(0.7, transit_jitter), 2),
                "on_time_delivery_pct": round(min(99.9, c["otd_pct"] * max(0.9, otd_jitter)), 2),
                "active":               bool(actives[i]),
            })

        df = pd.DataFrame(rows)
        self.state["dim_carrier"] = df
        self.logger.info(f"Generated dim_carrier: {len(df):,} rows")
        return df


# ── DIM_PRODUCT ────────────────────────────────────────────────────────────

class ProductDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("dim_product", {})
        active_ratio = dist.get("active_ratio", 0.82)

        catalog = CPG_PRODUCT_CATALOG
        ids     = self.uuids(n)
        actives = self.sample_bools(active_ratio, n)

        rows = []
        for i in range(n):
            # Cycle through catalog; add variant suffixes for variety
            base       = catalog[i % len(catalog)]
            variant_no = i // len(catalog)
            pkg_sizes  = ["", " 2-Pack", " 3-Pack", " 6-Pack", " Economy Size", " Club Pack"]
            suffix     = pkg_sizes[variant_no % len(pkg_sizes)]

            sku = f"{base['sku_prefix']}-{i:04d}"
            # Weight varies by variant
            weight = base["weight_kg"] * self.rng.uniform(0.8, 2.0 + variant_no * 0.3)

            rows.append({
                "product_id":     ids[i],
                "sku":            sku,
                "product_name":   base["product_name"] + suffix,
                "category":       base["category"],
                "sub_category":   base["sub_category"],
                "brand":          base["brand"],
                "unit_weight_kg": round(float(weight), 3),
                "packaging_type": base["packaging"],
                "active":         bool(actives[i]),
            })

        df = pd.DataFrame(rows)
        # Guarantee SKU uniqueness
        df["sku"] = df["sku"] + "-" + df.groupby("sku").cumcount().astype(str).replace("0", "")
        df["sku"] = df["sku"].str.rstrip("-")
        self.state["dim_product"] = df
        self.logger.info(f"Generated dim_product: {len(df):,} rows")
        return df


# ── DIM_CUSTOMER ───────────────────────────────────────────────────────────

class CustomerDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        dist = self.config["distributions"].get("dim_customer", {})
        active_ratio = dist.get("active_ratio", 0.88)

        ids     = self.uuids(n)
        actives = self.sample_bools(active_ratio, n)

        # Build a flat list of (name, segment, country, region, channel)
        customer_pool = []
        for segment, names in CUSTOMER_SEGMENTS.items():
            for name in names:
                channel = self.rng.choice(CUSTOMER_CHANNELS)
                # Assign geographies based on segment
                if "B2B" in segment or "Healthcare" in segment:
                    country, region = "United States", "North America"
                else:
                    country = self.rng.choice(
                        list(COUNTRY_REGION_MAP.keys()),
                        p=self._geo_weights()
                    )
                    region = COUNTRY_REGION_MAP[country]
                customer_pool.append((name, segment, country, region, channel))

        # Repeat pool if n > pool size
        pool = customer_pool * (n // len(customer_pool) + 1)

        rows = []
        for i in range(n):
            name, seg, country, region, channel = pool[i]
            suffix = f" ({i // len(customer_pool) + 1})" if i >= len(customer_pool) else ""
            rows.append({
                "customer_id":      ids[i],
                "customer_name":    name + suffix,
                "customer_segment": seg,
                "country":          country,
                "region":           region,
                "channel":          channel,
                "active":           bool(actives[i]),
            })

        df = pd.DataFrame(rows)
        self.state["dim_customer"] = df
        self.logger.info(f"Generated dim_customer: {len(df):,} rows")
        return df

    def _geo_weights(self) -> list[float]:
        """Weight countries toward North America and EMEA for CPG focus."""
        countries = list(COUNTRY_REGION_MAP.keys())
        weights   = []
        for c in countries:
            region = COUNTRY_REGION_MAP[c]
            if region == "North America":
                weights.append(0.40 / 3)
            elif region == "EMEA":
                weights.append(0.35 / 12)
            elif region == "APAC":
                weights.append(0.18 / 9)
            else:
                weights.append(0.07 / 5)
        # Normalise
        total = sum(weights)
        return [w / total for w in weights]


# ── DIM_DESTINATION ────────────────────────────────────────────────────────

class DestinationDimGenerator(BaseGenerator):

    def generate(self, n: int) -> pd.DataFrame:
        pool     = DESTINATION_DATA * (n // len(DESTINATION_DATA) + 1)
        selected = pool[:n]
        ids      = self.uuids(n)

        rows = []
        for i, d in enumerate(selected):
            suffix = f" #{i+1}" if i >= len(DESTINATION_DATA) else ""
            # Add small geographic jitter for uniqueness
            lat_jitter = self.rng.uniform(-0.5, 0.5)
            lon_jitter = self.rng.uniform(-0.5, 0.5)
            rows.append({
                "destination_id":   ids[i],
                "destination_name": d["name"] + suffix,
                "destination_type": d["type"],
                "country":          d["country"],
                "region":           COUNTRY_REGION_MAP.get(d["country"], "North America"),
                "lat":              round(d["lat"] + lat_jitter, 4),
                "lon":              round(d["lon"] + lon_jitter, 4),
            })

        df = pd.DataFrame(rows)
        self.state["dim_destination"] = df
        self.logger.info(f"Generated dim_destination: {len(df):,} rows")
        return df
