"""
Base Generator – Abstract base class for all CPG dimension and fact generators.
Provides shared sampling utilities, distribution helpers, and FK resolution.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import uuid

import numpy as np
import pandas as pd
from numpy.random import Generator

from utils.logger import get_logger

logger = get_logger("base_generator")


class BaseGenerator(ABC):
    """
    Abstract base for all table generators.

    Parameters
    ----------
    config : dict
        Merged configuration (schema + volumes + distributions + relationships).
    state : dict
        Shared mutable state; generators deposit their generated DataFrames here
        so downstream generators can resolve FK references.
    rng : numpy.random.Generator
        Seeded random number generator passed in for full reproducibility.
    """

    def __init__(self, config: dict, state: dict, rng: Generator):
        self.config = config
        self.state = state
        self.rng = rng
        self.logger = get_logger(self.__class__.__name__)

    # ── Public Interface ───────────────────────────────────────────────────

    @abstractmethod
    def generate(self, n: int) -> pd.DataFrame:
        """Generate n rows for this table and return a DataFrame."""
        ...

    # ── UUID Helpers ───────────────────────────────────────────────────────

    def uuids(self, n: int) -> list[str]:
        """Generate n unique UUID4 strings."""
        return [str(uuid.uuid4()) for _ in range(n)]

    # ── Distribution Samplers ──────────────────────────────────────────────

    def sample_normal(self, mean: float, std: float, n: int,
                      low: float = None, high: float = None) -> np.ndarray:
        vals = self.rng.normal(mean, std, n)
        if low is not None:
            vals = np.clip(vals, low, None)
        if high is not None:
            vals = np.clip(vals, None, high)
        return vals

    def sample_lognormal(self, mean: float, sigma: float, n: int,
                         low: float = None, high: float = None) -> np.ndarray:
        vals = self.rng.lognormal(mean, sigma, n)
        if low is not None:
            vals = np.clip(vals, low, None)
        if high is not None:
            vals = np.clip(vals, None, high)
        return vals

    def sample_beta(self, alpha: float, beta: float, n: int,
                    scale: float = 1.0) -> np.ndarray:
        """Beta distribution scaled to [0, scale]."""
        return self.rng.beta(alpha, beta, n) * scale

    def sample_uniform(self, low: float, high: float, n: int) -> np.ndarray:
        return self.rng.uniform(low, high, n)

    def sample_bools(self, true_probability: float, n: int) -> np.ndarray:
        return self.rng.random(n) < true_probability

    def sample_choice(self, choices: list, n: int,
                      weights: list[float] = None, replace: bool = True) -> np.ndarray:
        """Weighted random choice from a list."""
        if weights is not None:
            w = np.array(weights, dtype=float)
            w = w / w.sum()
        else:
            w = None
        return self.rng.choice(choices, size=n, replace=replace, p=w)

    def sample_choice_dict(self, weight_dict: dict, n: int) -> np.ndarray:
        """Weighted random choice from a {value: weight} dict."""
        choices = list(weight_dict.keys())
        weights = list(weight_dict.values())
        return self.sample_choice(choices, n, weights)

    # ── FK Resolution ──────────────────────────────────────────────────────

    def get_fk_pool(self, dim_table: str, pk_col: str,
                    active_only: bool = False,
                    active_col: str = "active") -> list:
        """
        Retrieve a list of PK values from an already-generated dimension table.
        Optionally filter to only active=True records.
        """
        if dim_table not in self.state:
            raise KeyError(
                f"Dimension '{dim_table}' not found in state. "
                f"Check generation_order in relationships.yaml."
            )
        df = self.state[dim_table]
        if active_only and active_col in df.columns:
            df = df[df[active_col]]
        return df[pk_col].tolist()

    def sample_fk(self, dim_table: str, pk_col: str,
                  n: int, strategy: str = "uniform",
                  pareto_factor: float = 0.20,
                  active_only: bool = False) -> np.ndarray:
        """
        Sample FK values from a dimension pool using a specified strategy.

        Strategies
        ----------
        uniform  : Equal probability across all keys.
        pareto   : Concentrate on top pareto_factor fraction of keys (80/20 rule).
        """
        pool = self.get_fk_pool(dim_table, pk_col, active_only=active_only)
        if not pool:
            raise ValueError(f"FK pool for '{dim_table}.{pk_col}' is empty.")

        if strategy == "pareto":
            # Split pool into "heavy" (top pareto_factor) and "tail"
            top_n = max(1, int(len(pool) * pareto_factor))
            heavy = pool[:top_n]
            tail  = pool[top_n:]
            # 80% of draws come from heavy keys
            n_heavy = int(n * 0.80)
            n_tail  = n - n_heavy
            heavy_vals = self.sample_choice(heavy, n_heavy)
            if tail:
                tail_vals = self.sample_choice(tail, n_tail)
            else:
                tail_vals = self.sample_choice(heavy, n_tail)
            combined = np.concatenate([heavy_vals, tail_vals])
            self.rng.shuffle(combined)
            return combined
        else:  # uniform
            return self.sample_choice(pool, n)

    # ── Rounding Helpers ───────────────────────────────────────────────────

    def round_float(self, arr: np.ndarray, decimals: int = 4) -> np.ndarray:
        return np.round(arr, decimals)

    def to_int(self, arr: np.ndarray) -> np.ndarray:
        return np.round(arr).astype(int)
