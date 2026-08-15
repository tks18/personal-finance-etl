import polars as pl


def safe_divide(
    numerator: str | pl.Expr, denominator: str | pl.Expr, default: float | None = 0.0
) -> pl.Expr:
    """Safely divides two columns/expressions, returning a default value if the denominator is 0 or null."""
    num_expr = pl.col(numerator) if isinstance(numerator, str) else numerator
    den_expr = pl.col(denominator) if isinstance(denominator, str) else denominator

    return pl.when(den_expr != 0).then(num_expr / den_expr).otherwise(pl.lit(default))


def pct_growth(col: str | pl.Expr, periods: int = 1, default: float | None = 0.0) -> pl.Expr:
    """Calculates the percentage growth of a column over a given number of periods."""
    expr = pl.col(col) if isinstance(col, str) else col
    shifted = expr.shift(periods)

    return (
        pl.when((shifted.is_not_null()) & (shifted != 0))
        .then((expr - shifted) / shifted)
        .otherwise(pl.lit(default))
    )


def rolling_avg(col: str | pl.Expr, window: int, by_col: str = "MONTH_START_DATE") -> pl.Expr:
    """Calculates the rolling mean of a column over a specified time window."""
    expr = pl.col(col) if isinstance(col, str) else col
    return expr.rolling_mean_by(by_col, window_size=f"{window}mo")


def rolling_std(col: str | pl.Expr, window: int, by_col: str = "MONTH_START_DATE") -> pl.Expr:
    """Calculates the rolling standard deviation of a column over a specified time window."""
    expr = pl.col(col) if isinstance(col, str) else col
    return expr.rolling_std_by(by_col, window_size=f"{window}mo")


def rolling_sum(col: str | pl.Expr, window: int, by_col: str = "MONTH_START_DATE") -> pl.Expr:
    """Calculates the rolling sum of a column over a specified time window."""
    expr = pl.col(col) if isinstance(col, str) else col
    return expr.rolling_sum_by(by_col, window_size=f"{window}mo")
