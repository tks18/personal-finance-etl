"""Simulation seed management and stochastic run provenance.

Owns
----
- derive_simulation_seed_offset: Generates deterministic 32-bit CRC hash offset from string root seed.
- derive_monthly_seed: Derives reproducible integer seed for a specific year and month.
- build_monthly_seed_expr: Polars expression generating reproducible seeds per temporal row.

Does not own
-------------
- Monte Carlo simulation kernel execution (owned by domain.fire.simulation).
- Global pipeline configuration (owned by config.financial_rules).
"""

from __future__ import annotations

import zlib

import polars as pl

__all__ = [
    "build_monthly_seed_expr",
    "derive_monthly_seed",
    "derive_simulation_seed_offset",
]


def derive_simulation_seed_offset(root_seed: str) -> int:
    """Derive a bounded deterministic hash offset from a seed string.

    Parameters
    ----------
    root_seed : str
        Arbitrary string seed identifying the simulation run.

    Returns
    -------
    int
        Hash offset in range [0, 999_999].
    """
    return zlib.crc32(root_seed.encode("utf-8")) % 1_000_000


def derive_monthly_seed(root_seed: str, year: int, month: int) -> int:
    """Derive a deterministic integer seed for a specific year and month.

    Parameters
    ----------
    root_seed : str
        Root seed identifying the run.
    year : int
        Calendar year.
    month : int
        Calendar month (1-12).

    Returns
    -------
    int
        Reproducible integer seed.
    """
    offset = derive_simulation_seed_offset(root_seed)
    return year * 12 + month + offset


def build_monthly_seed_expr(
    root_seed: str,
    year_col: str = "_temp_year",
    month_col: str = "_temp_month",
) -> pl.Expr:
    """Construct a Polars expression computing reproducible month-specific simulation seeds.

    Parameters
    ----------
    root_seed : str
        Root seed string for run isolation.
    year_col : str, default="_temp_year"
        Name of column containing calendar year.
    month_col : str, default="_temp_month"
        Name of column containing calendar month.

    Returns
    -------
    pl.Expr
        Polars integer expression.
    """
    offset = derive_simulation_seed_offset(root_seed)
    return (pl.col(year_col) * 12 + pl.col(month_col) + offset).cast(pl.Int32).alias("Seed_Int")
