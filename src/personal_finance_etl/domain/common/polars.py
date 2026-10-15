"""Reusable analytical Polars expressions and mathematical primitives.

Owns
----
- Safe division expression preventing ZeroDivisionError and NaN propagation.
- Percentage growth expressions across time periods.
- Rolling average, standard deviation, and rolling sum expressions over temporal windows.

Does not own
-------------
- Specific domain aggregation workflows (owned by domain.household, domain.investments, domain.tax).
- Schema definition or column mapping (owned by contracts or infrastructure.warehouse.schema).
"""

from __future__ import annotations

import polars as pl


def safe_divide(
    numerator: str | pl.Expr,
    denominator: str | pl.Expr,
    default: float | None = 0.0,
) -> pl.Expr:
    """Safely divide two columns/expressions, returning a default value if denominator is 0 or null.

    Parameters
    ----------
    numerator : str | pl.Expr
        Numerator column name or Polars expression.
    denominator : str | pl.Expr
        Denominator column name or Polars expression.
    default : float | None, default=0.0
        Fallback value when denominator is 0 or null.

    Returns
    -------
    pl.Expr
        Polars expression evaluating the safe division.
    """
    num_expr = pl.col(numerator) if isinstance(numerator, str) else numerator
    den_expr = pl.col(denominator) if isinstance(denominator, str) else denominator

    return pl.when(den_expr != 0).then(num_expr / den_expr).otherwise(pl.lit(default))


def pct_growth(
    col: str | pl.Expr,
    periods: int = 1,
    default: float | None = 0.0,
) -> pl.Expr:
    """Calculate percentage growth of a column over a given number of periods.

    Parameters
    ----------
    col : str | pl.Expr
        Column name or expression to compute growth for.
    periods : int, default=1
        Number of steps to shift backwards for comparison.
    default : float | None, default=0.0
        Fallback value if previous period is null or zero.

    Returns
    -------
    pl.Expr
        Polars expression evaluating (expr - shifted) / shifted.
    """
    expr = pl.col(col) if isinstance(col, str) else col
    shifted = expr.shift(periods)

    return (
        pl.when((shifted.is_not_null()) & (shifted != 0))
        .then((expr - shifted) / shifted)
        .otherwise(pl.lit(default))
    )


def rolling_avg(
    col: str | pl.Expr,
    window: int,
    by_col: str = "MONTH_START_DATE",
) -> pl.Expr:
    """Calculate rolling mean of a column over a specified month window.

    Parameters
    ----------
    col : str | pl.Expr
        Target column name or expression.
    window : int
        Window size in months (e.g., 3, 6, 12).
    by_col : str, default="MONTH_START_DATE"
        Temporal column name to order rolling computation by.

    Returns
    -------
    pl.Expr
        Polars rolling mean expression.
    """
    expr = pl.col(col) if isinstance(col, str) else col
    return expr.rolling_mean_by(by_col, window_size=f"{window}mo")


def rolling_std(
    col: str | pl.Expr,
    window: int,
    by_col: str = "MONTH_START_DATE",
) -> pl.Expr:
    """Calculate rolling standard deviation of a column over a specified month window.

    Parameters
    ----------
    col : str | pl.Expr
        Target column name or expression.
    window : int
        Window size in months.
    by_col : str, default="MONTH_START_DATE"
        Temporal column name to order rolling computation by.

    Returns
    -------
    pl.Expr
        Polars rolling standard deviation expression.
    """
    expr = pl.col(col) if isinstance(col, str) else col
    return expr.rolling_std_by(by_col, window_size=f"{window}mo")


def rolling_sum(
    col: str | pl.Expr,
    window: int,
    by_col: str = "MONTH_START_DATE",
) -> pl.Expr:
    """Calculate rolling sum of a column over a specified month window.

    Parameters
    ----------
    col : str | pl.Expr
        Target column name or expression.
    window : int
        Window size in months.
    by_col : str, default="MONTH_START_DATE"
        Temporal column name to order rolling computation by.

    Returns
    -------
    pl.Expr
        Polars rolling sum expression.
    """
    expr = pl.col(col) if isinstance(col, str) else col
    return expr.rolling_sum_by(by_col, window_size=f"{window}mo")

