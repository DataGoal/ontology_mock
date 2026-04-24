"""
Data Quality Validators for CPG Data Generator.
Validates generated DataFrames against schema rules and business constraints.
"""
from __future__ import annotations

import pandas as pd
from utils.logger import get_logger

logger = get_logger("validators")


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)
        logger.error(f"  [FAIL] {msg}")

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        logger.warning(f"  [WARN] {msg}")

    def summary(self) -> str:
        return (
            f"Validation: {'PASSED' if self.is_valid else 'FAILED'} | "
            f"Errors: {len(self.errors)} | Warnings: {len(self.warnings)}"
        )


def validate_table(df: pd.DataFrame, table_name: str, schema: dict) -> ValidationResult:
    """Run all validations on a generated DataFrame."""
    result = ValidationResult()
    columns_cfg = schema.get("columns", {})

    # 1. Check all expected columns are present
    for col in columns_cfg:
        if col not in df.columns:
            result.add_error(f"[{table_name}] Missing column: '{col}'")

    # 2. Null checks
    for col, cfg in columns_cfg.items():
        if col not in df.columns:
            continue
        if not cfg.get("nullable", True):
            null_count = df[col].isna().sum()
            if null_count > 0:
                result.add_error(
                    f"[{table_name}] Column '{col}' has {null_count} NULLs (nullable=false)"
                )

    # 3. Uniqueness checks
    for col, cfg in columns_cfg.items():
        if col not in df.columns:
            continue
        if cfg.get("unique") or cfg.get("pk"):
            dups = df[col].duplicated().sum()
            if dups > 0:
                result.add_error(
                    f"[{table_name}] Column '{col}' has {dups} duplicate values (unique constraint)"
                )

    # 4. Range checks for numeric fields
    for col, cfg in columns_cfg.items():
        if col not in df.columns:
            continue
        if "min" in cfg and pd.api.types.is_numeric_dtype(df[col]):
            violations = (df[col] < cfg["min"]).sum()
            if violations > 0:
                result.add_error(
                    f"[{table_name}] Column '{col}': {violations} values below min={cfg['min']}"
                )
        if "max" in cfg and pd.api.types.is_numeric_dtype(df[col]):
            violations = (df[col] > cfg["max"]).sum()
            if violations > 0:
                result.add_error(
                    f"[{table_name}] Column '{col}': {violations} values above max={cfg['max']}"
                )

    # 5. Row count check
    if len(df) == 0:
        result.add_error(f"[{table_name}] DataFrame is empty.")

    # 6. Warn on high null rates (>5% for nullable cols)
    for col in df.columns:
        null_rate = df[col].isna().mean()
        if null_rate > 0.05 and columns_cfg.get(col, {}).get("nullable", True):
            result.add_warning(
                f"[{table_name}] Column '{col}' has high null rate: {null_rate:.1%}"
            )

    return result


def validate_referential_integrity(
    fact_df: pd.DataFrame,
    fact_table: str,
    fk_col: str,
    dim_df: pd.DataFrame,
    dim_pk_col: str,
) -> ValidationResult:
    """Ensure all FK values in a fact table exist in the referenced dimension."""
    result = ValidationResult()
    orphan_count = (~fact_df[fk_col].isin(dim_df[dim_pk_col])).sum()
    if orphan_count > 0:
        result.add_error(
            f"[{fact_table}] FK '{fk_col}' has {orphan_count} orphaned references "
            f"(not found in {dim_pk_col})"
        )
    return result


def validate_business_rules(df: pd.DataFrame, table_name: str) -> ValidationResult:
    """Validate domain-specific business rules per table."""
    result = ValidationResult()

    if table_name == "fact_procurement":
        # total_cost should approximately equal quantity_delivered * unit_cost
        computed = (df["quantity_delivered"] * df["unit_cost"]).round(2)
        mismatch = (abs(df["total_cost"] - computed) > 1.0).sum()
        if mismatch > 0:
            result.add_warning(
                f"[{table_name}] {mismatch} rows where total_cost != quantity_delivered * unit_cost"
            )
        # delivery_variance_pct check
        neg_flag = (df["quantity_ordered"] <= 0).sum()
        if neg_flag > 0:
            result.add_error(f"[{table_name}] {neg_flag} rows with quantity_ordered <= 0")

    elif table_name == "fact_manufacturing":
        # units_produced should not exceed units_planned by more than 10%
        excess = (df["units_produced"] > df["units_planned"] * 1.10).sum()
        if excess > 0:
            result.add_warning(
                f"[{table_name}] {excess} rows where units_produced > 110% of units_planned"
            )
        # downtime + utilization cross-check
        high_util_high_downtime = (
            (df["machine_utilization_pct"] > 95) & (df["downtime_hours"] > 4)
        ).sum()
        if high_util_high_downtime > 0:
            result.add_warning(
                f"[{table_name}] {high_util_high_downtime} rows with util>95% AND downtime>4h"
            )

    elif table_name == "fact_inventory":
        # stockout_flag and overstock_flag should not both be 1
        both_flags = ((df["stockout_flag"] == 1) & (df["overstock_flag"] == 1)).sum()
        if both_flags > 0:
            result.add_error(
                f"[{table_name}] {both_flags} rows with stockout_flag=1 AND overstock_flag=1"
            )
        # safety_stock must be <= reorder_point
        ss_gt_rop = (df["safety_stock"] > df["reorder_point"]).sum()
        if ss_gt_rop > 0:
            result.add_warning(
                f"[{table_name}] {ss_gt_rop} rows where safety_stock > reorder_point"
            )

    elif table_name == "fact_shipment":
        # quantity_received cannot exceed quantity_shipped
        over_received = (df["quantity_received"] > df["quantity_shipped"] * 1.02).sum()
        if over_received > 0:
            result.add_warning(
                f"[{table_name}] {over_received} rows where quantity_received > quantity_shipped"
            )

    elif table_name == "fact_sales_demand":
        # fulfillment_rate_pct = units_fulfilled / units_demanded * 100
        computed = (df["units_fulfilled"] / df["units_demanded"].replace(0, pd.NA) * 100).round(2)
        mismatch = (abs(df["fulfillment_rate_pct"] - computed) > 1.0).dropna().sum()
        if mismatch > 0:
            result.add_warning(
                f"[{table_name}] {mismatch} rows where fulfillment_rate_pct is inconsistent"
            )

    return result
