"""
CPG Data Generator Pipeline Orchestrator.

Responsibilities:
  1. Load and merge all YAML configs.
  2. Instantiate generators in dependency order (dims → facts).
  3. Run each generator and collect DataFrames into shared state.
  4. Validate generated data (schema + RI + business rules).
  5. Hand off DataFrames to the Writer.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from src.generators.dim_generators import (
    DateDimGenerator, VendorDimGenerator, PlantDimGenerator,
    ShiftDimGenerator, WarehouseDimGenerator, CarrierDimGenerator,
    ProductDimGenerator, CustomerDimGenerator, DestinationDimGenerator,
)
from src.generators.fact_generators import (
    ProcurementFactGenerator, ManufacturingFactGenerator,
    InventoryFactGenerator, ShipmentFactGenerator, SalesDemandFactGenerator,
)
from src.writer import DataWriter, DatabricksWriter
from utils.validators import validate_table, validate_referential_integrity, validate_business_rules
from utils.logger import get_logger

logger = get_logger("pipeline")

# Map table names to generator classes
GENERATOR_REGISTRY = {
    "dim_date":           DateDimGenerator,
    "dim_vendor":         VendorDimGenerator,
    "dim_plant":          PlantDimGenerator,
    "dim_shift":          ShiftDimGenerator,
    "dim_warehouse":      WarehouseDimGenerator,
    "dim_carrier":        CarrierDimGenerator,
    "dim_product":        ProductDimGenerator,
    "dim_customer":       CustomerDimGenerator,
    "dim_destination":    DestinationDimGenerator,
    "fact_procurement":   ProcurementFactGenerator,
    "fact_manufacturing": ManufacturingFactGenerator,
    "fact_inventory":     InventoryFactGenerator,
    "fact_shipment":      ShipmentFactGenerator,
    "fact_sales_demand":  SalesDemandFactGenerator,
}

# FK relationships for referential integrity checks
FK_RELATIONSHIPS = {
    "fact_procurement":   [("vendor_id", "dim_vendor", "vendor_id"),
                           ("product_id", "dim_product", "product_id"),
                           ("date_id", "dim_date", "date_id"),
                           ("warehouse_id", "dim_warehouse", "warehouse_id")],
    "fact_manufacturing": [("plant_id", "dim_plant", "plant_id"),
                           ("product_id", "dim_product", "product_id"),
                           ("date_id", "dim_date", "date_id"),
                           ("shift_id", "dim_shift", "shift_id")],
    "fact_inventory":     [("warehouse_id", "dim_warehouse", "warehouse_id"),
                           ("product_id", "dim_product", "product_id"),
                           ("date_id", "dim_date", "date_id")],
    "fact_shipment":      [("carrier_id", "dim_carrier", "carrier_id"),
                           ("product_id", "dim_product", "product_id"),
                           ("date_id", "dim_date", "date_id"),
                           ("origin_warehouse_id", "dim_warehouse", "warehouse_id"),
                           ("destination_id", "dim_destination", "destination_id")],
    "fact_sales_demand":  [("product_id", "dim_product", "product_id"),
                           ("customer_id", "dim_customer", "customer_id"),
                           ("date_id", "dim_date", "date_id"),
                           ("destination_id", "dim_destination", "destination_id")],
}


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _merge_config(configs_dir: str) -> dict:
    """Load and merge all YAML configuration files into a single config dict."""
    base = Path(configs_dir)
    return {
        "schema":        _load_yaml(base / "schema.yaml"),
        "volumes":       _load_yaml(base / "data_volumes.yaml"),
        "distributions": _load_yaml(base / "distributions.yaml"),
        "relationships": _load_yaml(base / "relationships.yaml"),
    }


def _get_row_counts(config: dict) -> dict[str, int]:
    """Extract row counts for the active profile."""
    vols    = config["volumes"]
    profile = vols["active_profile"]
    pcfg    = vols["profiles"][profile]
    dims    = pcfg["dimensions"]
    facts   = pcfg["facts"]
    return {**dims, **facts}


class CPGDataPipeline:
    """
    Orchestrates the full CPG data generation lifecycle.

    Usage
    -----
    >>> pipeline = CPGDataPipeline(configs_dir="configs", output_dir="output")
    >>> results  = pipeline.run()
    """

    def __init__(
        self,
        configs_dir: str = "configs",
        output_dir: str = None,
        writer: "DataWriter | DatabricksWriter | None" = None,
    ):
        """
        Parameters
        ----------
        configs_dir : str
            Path to the directory containing schema.yaml, data_volumes.yaml,
            distributions.yaml, and relationships.yaml.  Accepts local paths
            and DBFS paths (e.g. '/dbfs/FileStore/ontology_mock/configs').
        output_dir : str, optional
            Local output directory used by the default DataWriter.
            Ignored when a custom ``writer`` is supplied.
        writer : DataWriter | DatabricksWriter, optional
            Pre-built writer instance.  Pass a ``DatabricksWriter`` to write
            directly to Delta tables in Databricks.  When omitted, a
            ``DataWriter`` (local file output) is created automatically.
        """
        self.config = _merge_config(configs_dir)
        self.state: dict = {}  # shared state: table_name → DataFrame

        # Set random seed for reproducibility
        seed = self.config["volumes"].get("random_seed", 42)
        self.rng = np.random.default_rng(seed)
        logger.info(f"Random seed: {seed}")

        # Use the injected writer when provided; otherwise create a local DataWriter
        if writer is not None:
            self.writer = writer
            self.output_dir = writer.output_location
        else:
            out_cfg = self.config["volumes"].get("output", {})
            self.output_dir = output_dir or out_cfg.get("output_dir", "./output")
            self.writer = DataWriter(
                output_dir=self.output_dir,
                fmt=out_cfg.get("format", "csv"),
                compress=out_cfg.get("compress", False),
            )

        # Determine generation order and row counts
        self.generation_order = self.config["relationships"]["generation_order"]
        self.row_counts = _get_row_counts(self.config)

        profile = self.config["volumes"]["active_profile"]
        logger.info(f"Active profile: '{profile}'")
        logger.info(f"Generation order: {self.generation_order}")

    # ── Public API ─────────────────────────────────────────────────────────

    def run(self, write: bool = True, validate: bool = True) -> dict:
        """Run the full pipeline: generate → validate → write."""
        pipeline_start = time.time()
        results = {}

        logger.info("=" * 60)
        logger.info("CPG DATA GENERATOR PIPELINE STARTED")
        logger.info("=" * 60)

        # ── Phase 1: Generate ──────────────────────────────────────────────
        for table_name in self.generation_order:
            df = self._generate_table(table_name)
            if df is not None:
                results[table_name] = df

        # ── Phase 2: Validate ──────────────────────────────────────────────
        if validate:
            self._validate_all(results)

        # ── Phase 3: Write ─────────────────────────────────────────────────
        if write:
            self._write_all(results)

        elapsed = time.time() - pipeline_start
        total_rows = sum(len(df) for df in results.values())
        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE | Tables: {len(results)} | "
                    f"Total rows: {total_rows:,} | Elapsed: {elapsed:.1f}s")
        logger.info("=" * 60)

        return results

    # ── Phase Implementations ──────────────────────────────────────────────

    def _generate_table(self, table_name: str):
        if table_name not in GENERATOR_REGISTRY:
            logger.warning(f"No generator found for '{table_name}' – skipping.")
            return None

        n = self.row_counts.get(table_name)
        gen_cls = GENERATOR_REGISTRY[table_name]
        generator = gen_cls(config=self.config, state=self.state, rng=self.rng)

        t0 = time.time()
        try:
            if table_name == "dim_date":
                # Date dim ignores n; uses date range
                df = generator.generate(n)
            elif table_name == "dim_shift":
                # Shift dim is always 3 rows
                df = generator.generate(3)
            else:
                df = generator.generate(n)

            elapsed_ms = (time.time() - t0) * 1000
            logger.info(f"  ✓ {table_name:<25} {len(df):>8,} rows  ({elapsed_ms:.0f}ms)")
            return df

        except Exception as exc:
            logger.error(f"  ✗ {table_name}: FAILED – {exc}")
            raise

    def _validate_all(self, results: dict):
        logger.info("")
        logger.info("── VALIDATION PHASE ──────────────────────────────────")
        all_passed = True

        for table_name, df in results.items():
            # Schema validation
            schema_tables = {
                **self.config["schema"].get("dimensions", {}),
                **self.config["schema"].get("facts", {}),
            }
            if table_name in schema_tables:
                schema = schema_tables[table_name]
                result = validate_table(df, table_name, schema)
                if not result.is_valid:
                    all_passed = False

            # Business rule validation
            br_result = validate_business_rules(df, table_name)
            if not br_result.is_valid:
                all_passed = False

        # Referential integrity checks
        for fact_table, fk_list in FK_RELATIONSHIPS.items():
            if fact_table not in results:
                continue
            fact_df = results[fact_table]
            for fk_col, dim_table, dim_pk in fk_list:
                if dim_table not in results:
                    continue
                ri = validate_referential_integrity(
                    fact_df, fact_table, fk_col, results[dim_table], dim_pk
                )
                if not ri.is_valid:
                    all_passed = False

        status = "ALL CHECKS PASSED ✓" if all_passed else "SOME CHECKS FAILED ✗"
        logger.info(f"Validation summary: {status}")
        logger.info("")

    def _write_all(self, results: dict):
        logger.info("── WRITE PHASE ───────────────────────────────────────")
        for table_name, df in results.items():
            self.writer.write(df, table_name)
        logger.info(f"All tables written to: {self.writer.output_location}")
        logger.info("")
