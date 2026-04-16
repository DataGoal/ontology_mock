"""
Data Writer – writes generated DataFrames to disk in CSV, Parquet, or JSON format.
Supports optional gzip compression for Parquet.
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
