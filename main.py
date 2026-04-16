"""
CPG Supply Chain Data Generator – Main Entry Point

Usage:
  python main.py                         # Use dev profile, write CSV
  python main.py --profile staging       # Use staging profile
  python main.py --profile prod --format parquet --compress
  python main.py --no-write              # Generate and validate only (no files)
  python main.py --no-validate           # Skip validation phase
  python main.py --output ./my_output    # Custom output directory
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import CPGDataPipeline
from utils.logger import get_logger

logger = get_logger("main", log_file="./output/generator.log")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CPG Supply Chain Mock Data Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--profile",
        default=None,
        choices=["dev", "staging", "prod"],
        help="Data volume profile to use (overrides active_profile in data_volumes.yaml)",
    )
    parser.add_argument(
        "--format",
        default=None,
        choices=["csv", "parquet", "json"],
        help="Output file format (overrides config)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory path (overrides config)",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Enable gzip compression for parquet output",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Generate and validate data without writing to disk",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip the validation phase (faster for large profiles)",
    )
    parser.add_argument(
        "--configs-dir",
        default="configs",
        help="Path to the configs directory (default: ./configs)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("CPG SUPPLY CHAIN DATA GENERATOR")
    logger.info("=" * 60)

    # Build pipeline
    pipeline = CPGDataPipeline(
        configs_dir=args.configs_dir,
        output_dir=args.output,
    )

    # Apply CLI overrides
    if args.profile:
        pipeline.config["volumes"]["active_profile"] = args.profile
        from src.pipeline import _get_row_counts
        pipeline.row_counts = _get_row_counts(pipeline.config)
        logger.info(f"Profile overridden via CLI: '{args.profile}'")

    if args.format:
        pipeline.writer.fmt = args.format
        logger.info(f"Output format overridden via CLI: '{args.format}'")

    if args.compress:
        pipeline.writer.compress = True
        logger.info("Compression enabled.")

    # Run pipeline
    results = pipeline.run(
        write=not args.no_write,
        validate=not args.no_validate,
    )

    # Summary
    logger.info("\nGenerated Tables:")
    logger.info(f"  {'Table':<30} {'Rows':>10}")
    logger.info(f"  {'-'*30} {'-'*10}")
    for table_name, df in results.items():
        logger.info(f"  {table_name:<30} {len(df):>10,}")

    total = sum(len(df) for df in results.values())
    logger.info(f"\n  {'TOTAL':<30} {total:>10,}")

    if not args.no_write:
        out_dir = args.output or pipeline.output_dir
        logger.info(f"\nOutput files written to: {out_dir}/")


if __name__ == "__main__":
    main()
