"""Logging configuration for CPG Data Generator."""
import logging
import sys
from pathlib import Path


def get_logger(name: str, log_level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Return a configured logger with console and optional file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Avoid duplicate handlers on re-import

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (optional)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
