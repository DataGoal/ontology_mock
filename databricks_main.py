# Databricks notebook source
"""
CPG Supply Chain Data Generator – Databricks Notebook Entry Point

This file is designed to run inside Databricks as a notebook (each
submitted to a Databricks Job.

Quick start
-----------
1. Clone this repo into Databricks Repos:
       Workspace → Repos → Add Repo → paste your git URL

2. Attach the notebook to a cluster running DBR 12.x+ (or later).
   The cluster must have internet access to install PyPI packages,
   or the packages below must be pre-installed as cluster libraries.

3. Run Cell 1 once to install Python dependencies (restart required).

4. Set the widgets in Cell 2 and run all remaining cells.

Alternatively, submit as a Databricks Job:
   - Task type: Python script
   - Source: Workspace / Repos path to this file
   - Parameters: pass as job parameters (widgets are read from
     spark.conf or environment variables when dbutils is unavailable)
"""

# COMMAND ----------

# Cell 1 – Install Python dependencies
# Run this cell once, then restart the Python process / kernel.
# PySpark is provided by the Databricks runtime and must NOT be listed here.

%pip install pyyaml>=6.0.1 numpy>=1.26.0 pandas>=2.1.0 pyarrow>=14.0.0 tqdm>=4.66.0

# COMMAND ----------

# Cell 2 – Bootstrap: add project root to sys.path

import sys
import os
from pathlib import Path

# When running from Databricks Repos the __file__ is the notebook path.
# Fall back to the current working directory if __file__ is not available.
try:
    _project_root = str(Path(__file__).resolve().parent)
except NameError:
    _project_root = os.getcwd()

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

print(f"Project root: {_project_root}")

# COMMAND ----------

# Cell 3 – Parameters via Databricks widgets
#
# Widgets appear as dropdowns / text boxes at the top of the notebook.
# When running as a Job, set these values in the job's task parameters.

try:
    dbutils  # type: ignore[name-defined]  # noqa: F821
    _in_databricks = True
except NameError:
    _in_databricks = False

if _in_databricks:
    dbutils.widgets.removeAll()
    dbutils.widgets.text(
        "profile", "dev",
        "Profile (dev / staging / prod)"
    )
    dbutils.widgets.text(
        "catalog", "",
        "Unity Catalog name (leave blank for Hive Metastore)"
    )
    dbutils.widgets.text(
        "db_schema", "cpg_supply_chain",
        "Database / schema name"
    )
    dbutils.widgets.text(
        "configs_path", "configs",
        "Path to configs directory (relative or /dbfs/... absolute)"
    )
    dbutils.widgets.dropdown(
        "write_mode", "overwrite", ["overwrite", "append"],
        "Delta write mode"
    )
    dbutils.widgets.dropdown(
        "validate", "true", ["true", "false"],
        "Run data validation?"
    )

    PROFILE      = dbutils.widgets.get("profile").strip() or "dev"
    CATALOG      = dbutils.widgets.get("catalog").strip() or "nike_databricks"
    DB_SCHEMA    = dbutils.widgets.get("db_schema").strip() or "cpg_supply_chain"
    CONFIGS_PATH = dbutils.widgets.get("configs_path").strip() or "configs"
    WRITE_MODE   = dbutils.widgets.get("write_mode").strip()
    VALIDATE     = dbutils.widgets.get("validate").strip().lower() == "true"
else:
    # Fallback for local testing outside Databricks
    PROFILE      = os.getenv("PROFILE", "dev")
    CATALOG      = os.getenv("CATALOG") or None
    DB_SCHEMA    = os.getenv("DB_SCHEMA", "cpg_supply_chain")
    CONFIGS_PATH = os.getenv("CONFIGS_PATH", "configs")
    WRITE_MODE   = os.getenv("WRITE_MODE", "overwrite")
    VALIDATE     = os.getenv("VALIDATE", "true").lower() == "true"

print("=" * 50)
print("CPG Supply Chain Data Generator – Databricks")
print("=" * 50)
print(f"  Profile      : {PROFILE}")
print(f"  Catalog      : {CATALOG or '(Hive Metastore)'}")
print(f"  Schema       : {DB_SCHEMA}")
print(f"  Configs path : {CONFIGS_PATH}")
print(f"  Write mode   : {WRITE_MODE}")
print(f"  Validate     : {VALIDATE}")
print("=" * 50)

# COMMAND ----------

# Cell 4 – Run the pipeline

from src.pipeline import CPGDataPipeline, _get_row_counts
from src.writer import DatabricksWriter

# Build the Databricks writer – creates the schema if it does not exist
db_writer = DatabricksWriter(
    schema=DB_SCHEMA,
    catalog=CATALOG,
    mode=WRITE_MODE,
)

# Build the pipeline, injecting the Databricks writer
pipeline = CPGDataPipeline(configs_dir=CONFIGS_PATH, writer=db_writer)

# Override the data volume profile
pipeline.config["volumes"]["active_profile"] = PROFILE
pipeline.row_counts = _get_row_counts(pipeline.config)

# Execute: generate → (optionally validate) → write to Delta tables
results = pipeline.run(write=True, validate=VALIDATE)

# COMMAND ----------

# Cell 5 – Print summary

print("\nGenerated Tables:")
print(f"  {'Table':<30} {'Rows':>10}")
print(f"  {'-'*30} {'-'*10}")
for table_name, df in results.items():
    print(f"  {table_name:<30} {len(df):>10,}")
total = sum(len(df) for df in results.values())
print(f"\n  {'TOTAL':<30} {total:>10,}")
print(f"\nAll tables written to: {db_writer.output_location}")

# COMMAND ----------

# Cell 6 – (Optional) Quick sanity-check query
#
# Uncomment and run after the pipeline completes to verify the data.
#
# spark.sql(f"SELECT COUNT(*) AS n FROM {db_writer.output_location}.`dim_product`").show()
# spark.sql(f"SELECT COUNT(*) AS n FROM {db_writer.output_location}.`fact_sales_demand`").show()
