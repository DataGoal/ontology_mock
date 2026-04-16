"""
Data Writer – writes generated DataFrames to disk in CSV, Parquet, or JSON format.
Supports optional gzip compression for Parquet.

Also provides DatabricksWriter for writing directly to Delta tables in Databricks.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.logger import get_logger

logger = get_logger("writer")


class DataWriter:
    """
    Writes DataFrames to the configured output directory.

    Parameters
    ----------
    output_dir : str
        Root output directory.
    fmt : str
        One of 'csv', 'parquet', 'json'.
    compress : bool
        If True and format is parquet, apply snappy/gzip compression.
    """

    SUPPORTED_FORMATS = {"csv", "parquet", "json"}

    def __init__(self, output_dir: str = "./output", fmt: str = "csv", compress: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        fmt = fmt.lower()
        if fmt not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{fmt}'. Choose from: {self.SUPPORTED_FORMATS}")
        self.fmt = fmt
        self.compress = compress

    @property
    def output_location(self) -> str:
        return str(self.output_dir)

    def write(self, df: pd.DataFrame, table_name: str) -> Path:
        """Write a DataFrame to disk and return the output path."""
        ext   = self._extension()
        fname = f"{table_name}.{ext}"
        path  = self.output_dir / fname

        if self.fmt == "csv":
            df.to_csv(path, index=False, encoding="utf-8")

        elif self.fmt == "parquet":
            compression = "gzip" if self.compress else "snappy"
            df.to_parquet(path, index=False, compression=compression)

        elif self.fmt == "json":
            df.to_json(path, orient="records", lines=True, date_format="iso")

        size_kb = path.stat().st_size / 1024
        logger.info(f"  → {fname:<45} ({size_kb:.1f} KB)")
        return path

    def _extension(self) -> str:
        if self.fmt == "csv":     return "csv"
        if self.fmt == "parquet": return "parquet"
        if self.fmt == "json":    return "jsonl"
        return "dat"


class DatabricksWriter:
    """
    Writes DataFrames as Delta tables in Databricks (Unity Catalog or Hive Metastore).

    Parameters
    ----------
    schema : str
        Database / schema name (default: 'cpg_supply_chain').
    catalog : str or None
        Unity Catalog name. Leave None to use the Hive Metastore.
    mode : str
        Spark write mode – 'overwrite' (default) or 'append'.

    Usage (inside a Databricks notebook or job)
    --------------------------------------------
    >>> from src.writer import DatabricksWriter
    >>> writer = DatabricksWriter(schema="cpg_supply_chain", catalog="my_catalog")
    >>> writer.write(df, "dim_product")
    """

    def __init__(
        self,
        schema: str = "cpg_supply_chain",
        catalog: str | None = None,
        mode: str = "overwrite",
    ):
        try:
            from pyspark.sql import SparkSession  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "pyspark is not installed. DatabricksWriter requires a Databricks runtime."
            ) from exc

        self.spark = SparkSession.getActiveSession()
        if self.spark is None:
            raise RuntimeError(
                "No active SparkSession found. Run DatabricksWriter inside Databricks."
            )

        self.catalog = catalog
        self.schema  = schema
        self.mode    = mode

        # Create catalog (Unity Catalog only) and schema if they do not exist
        if catalog:
            self.spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")
            self.spark.sql(f"USE CATALOG `{catalog}`")

        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{schema}`")

        self._full_schema = f"`{catalog}`.`{schema}`" if catalog else f"`{schema}`"
        logger.info(f"DatabricksWriter initialised → target schema: {self._full_schema}")

    @property
    def output_location(self) -> str:
        return self._full_schema

    def write(self, df: pd.DataFrame, table_name: str) -> str:
        """
        Convert a pandas DataFrame to a Spark DataFrame and write it as a
        Delta table.  Returns the fully-qualified table name.
        """
        full_table = f"{self._full_schema}.`{table_name}`"
        spark_df = self.spark.createDataFrame(df)

        (
            spark_df.write
            .format("delta")
            .mode(self.mode)
            .option("overwriteSchema", "true")
            .saveAsTable(full_table)
        )

        logger.info(f"  → {full_table:<55} ({df.shape[0]:,} rows)")
        return full_table
