"""Macroeconomic, Capital Market, and FIRE forecasting assumption models.

Owns
----
- Macroeconomic assumptions (trading days, fallback inflation, risk-free rate, marginal tax slab).
- Financial Independence Retire Early (FIRE) assumptions (SWR multiplier, Coast/Lean FI, CAPE).
- Stochastic simulation configs (Markov regime switching, human capital shock, glide path, jump diffusion, Guyton-Klinger, inflation).
- Monte Carlo simulation boundaries and parameters.
- Capital Market Assumptions (CMA) and portfolio target allocations.
- Root AssumptionsRules grouping macro, fire, monte_carlo, tax, and cma.

Does not own
-------------
- Tax statutory rates and head classifications (owned by config.financial_rules.tax).
- Household income/expense policies (owned by config.financial_rules.household).
- Mathematical execution of Monte Carlo or stochastic engines (owned by domain.fire).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from personal_finance_etl.config.financial_rules.tax import TaxAssumptions


class MacroAssumptions(BaseModel):
    """Baseline macroeconomic parameter configuration for annualization and fallbacks."""

    default_trading_days: float = Field(
        ...,
        description="Default number of trading days in a year for annualized volatility calculations.",
        json_schema_extra={"min": 200.0, "max": 365.0, "step": 1.0, "unit": "days"},
    )
    fallback_inflation_rate: float = Field(
        ...,
        description="Fallback annualized inflation rate if historical macro data is unavailable.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 0.50,
            "step": 0.005,
            "unit": "%",
        },
    )
    fallback_risk_free_rate: float = Field(
        ...,
        description="Fallback annualized risk-free rate if historical macro data is unavailable.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 0.50,
            "step": 0.005,
            "unit": "%",
        },
    )
    fallback_ordinary_income_rate: float = Field(
        default=0.30,
        description="Fallback ordinary income tax rate (marginal slab) if not found in macro table.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 1.0,
            "step": 0.01,
            "unit": "%",
        },
    )


class FireAssumptions(BaseModel):
    """Financial Independence and Safe Withdrawal Rate forecasting rules."""

    swr_multiplier: float = Field(
        ...,
        description="Safe Withdrawal Rate multiplier (e.g., 25.0 for 4% rule).",
        json_schema_extra={"min": 10.0, "max": 100.0, "step": 0.5, "unit": "x"},
    )
    coast_fi_real_return: float = Field(
        ...,
        description="Assumed real (inflation-adjusted) return for Coast FI calculations.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 0.30,
            "step": 0.005,
            "unit": "%",
        },
    )
    coast_fi_years: int = Field(
        ...,
        description="Number of years to coast (compound) for Coast FI.",
        json_schema_extra={"min": 1, "max": 50, "step": 1, "unit": "years"},
    )
    lean_fi_ratio: float = Field(
        ...,
        description="Ratio of Target FI considered sufficient for Lean FI.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.1,
            "max": 1.5,
            "step": 0.05,
            "unit": "ratio",
        },
    )
    fallback_trailing_return: float = Field(
        ...,
        description="Fallback nominal return to use for FIRE forecasting if historical returns are unavailable.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 0.50,
            "step": 0.005,
            "unit": "%",
        },
    )

    cape_swr_floor: float = Field(
        ...,
        description="Floor SWR during severe drawdown.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.01,
            "max": 0.10,
            "step": 0.0025,
            "unit": "%",
        },
    )
    cape_swr_ceiling: float = Field(
        ...,
        description="Ceiling SWR during moderate drawdown.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.01,
            "max": 0.10,
            "step": 0.0025,
            "unit": "%",
        },
    )
    cape_swr_base: float = Field(
        ...,
        description="Base SWR during normal markets.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.01,
            "max": 0.10,
            "step": 0.0025,
            "unit": "%",
        },
    )
    human_capital_max_age: float = Field(
        ...,
        description="Maximum age until which you expect to be healthy and working.",
        json_schema_extra={"min": 30.0, "max": 80.0, "step": 1.0, "unit": "years"},
    )
    human_capital_discount_rate: float = Field(
        ...,
        description="Discount rate for human capital.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.01,
            "max": 0.20,
            "step": 0.005,
            "unit": "%",
        },
    )


class MarkovRegimeConfig(BaseModel):
    """Three-state Markov regime switching parameters (Bull, Bear, Stagflation)."""

    transition_matrix: list[list[float]] = Field(
        default=[
            [0.90, 0.08, 0.02],
            [0.15, 0.80, 0.05],
            [0.10, 0.15, 0.75],
        ],
        description="3x3 Matrix for probabilities of transitioning between Bull, Bear, and Stagflation states.",
        json_schema_extra={"ui_widget": "matrix_3x3"},
    )
    state_bull: tuple[float, float, float] = Field(
        default=(0.10, 0.12, 0.04),
        description="Bull Market parameters: (drift, volatility, inflation target)",
        json_schema_extra={"ui_widget": "tuple_3"},
    )
    state_bear: tuple[float, float, float] = Field(
        default=(-0.15, 0.25, 0.02),
        description="Bear Market parameters: (drift, volatility, inflation target)",
        json_schema_extra={"ui_widget": "tuple_3"},
    )
    state_stag: tuple[float, float, float] = Field(
        default=(-0.05, 0.18, 0.08),
        description="Stagflation parameters: (drift, volatility, inflation target)",
        json_schema_extra={"ui_widget": "tuple_3"},
    )


class HumanCapitalConfig(BaseModel):
    """Human capital income shock probabilities and severance coverage parameters."""

    shock_probability: float = Field(
        default=0.20,
        description="Probability of an income shock (job loss, zero bonus) when in Bear or Stagflation states.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "unit": "%",
        },
    )
    shock_duration_min: int = Field(
        default=6,
        description="Minimum duration (in months) of the income shock.",
        json_schema_extra={"min": 1, "max": 60, "step": 1, "unit": "months"},
    )
    shock_duration_max: int = Field(
        default=12,
        description="Maximum duration (in months) of the income shock.",
        json_schema_extra={"min": 1, "max": 60, "step": 1, "unit": "months"},
    )
    unemployment_benefit_coverage_pct: float = Field(
        default=0.0,
        description="Percentage of core expenses covered by unemployment benefits or severance during a shock.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "unit": "%",
        },
    )


class GlidePathConfig(BaseModel):
    """Retirement asset allocation glide path, de-risking, and debt buffer rules."""

    derisk_start_months_prior: int = Field(
        default=60,
        description="Months prior to the FI target date to begin de-risking the portfolio.",
        json_schema_extra={"min": 0, "max": 240, "step": 6, "unit": "months"},
    )
    post_fi_re_risk_months: int = Field(
        default=120,
        description="Months after reaching FI to slowly re-risk the portfolio back to base.",
        json_schema_extra={"min": 0, "max": 240, "step": 6, "unit": "months"},
    )
    base_equity_weight: float = Field(
        default=0.70,
        description="Base/maximum equity allocation weight (e.g., 70%).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "unit": "%",
        },
    )
    fi_target_equity_weight: float = Field(
        default=0.40,
        description="Target minimum equity allocation weight upon reaching FI (e.g., 40%).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "unit": "%",
        },
    )
    debt_real_return: float = Field(
        default=0.02,
        description="Expected real return for the non-equity (debt) portion of the glide path.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": -0.10,
            "max": 0.20,
            "step": 0.005,
            "unit": "%",
        },
    )
    debt_volatility: float = Field(
        default=0.04,
        description="Expected volatility for the non-equity (debt) portion of the glide path.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.001,
            "max": 0.30,
            "step": 0.005,
            "unit": "%",
        },
    )
    dynamic_debt_drawdown_first: bool = Field(
        default=False,
        description="If True, during decumulation down-months, withdrawals are taken from debt, bypassing equity liquidation.",
        json_schema_extra={
            "ui_widget": "switch",
            "active_label": "Drawdown Debt First",
            "inactive_label": "Standard Liquidation",
        },
    )


class JumpDiffusionConfig(BaseModel):
    """Black Swan jump diffusion crash parameters and investment fee drag."""

    jump_probability_annual: float = Field(
        default=0.05,
        description="Annual probability of a Black Swan market crash (e.g., 5%).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 1.0,
            "step": 0.01,
            "unit": "%",
        },
    )
    jump_magnitude: float = Field(
        default=-0.20,
        description="The magnitude of the crash when a jump occurs (e.g., -20%).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": -0.90,
            "max": 0.0,
            "step": 0.05,
            "unit": "%",
        },
    )
    expense_ratio_drag: float = Field(
        default=0.005,
        description="Annual portfolio expense ratio or fee drag deducted from returns (e.g., 50 bps).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.0,
            "max": 0.05,
            "step": 0.001,
            "unit": "%",
        },
    )


class GuytonKlingerConfig(BaseModel):
    """Guyton-Klinger dynamic withdrawal rules and capital preservation guardrails."""

    withdrawal_upper_threshold: float = Field(
        default=1.2,
        description="Multiplier over initial SWR to trigger a lifestyle cut (e.g., 1.2 for +20%).",
        json_schema_extra={"min": 1.0, "max": 2.0, "step": 0.05, "unit": "ratio"},
    )
    withdrawal_lower_threshold: float = Field(
        default=0.8,
        description="Multiplier under initial SWR to trigger a lifestyle raise (e.g., 0.8 for -20%).",
        json_schema_extra={"min": 0.1, "max": 1.0, "step": 0.05, "unit": "ratio"},
    )
    lifestyle_cut_multiplier: float = Field(
        default=0.90,
        description="Multiplier for withdrawal amount when cutting lifestyle (e.g., 0.90 for -10%).",
        json_schema_extra={"min": 0.5, "max": 1.0, "step": 0.05, "unit": "multiplier"},
    )
    lifestyle_raise_multiplier: float = Field(
        default=1.10,
        description="Multiplier for withdrawal amount when raising lifestyle (e.g., 1.10 for +10%).",
        json_schema_extra={"min": 1.0, "max": 1.5, "step": 0.05, "unit": "multiplier"},
    )


class InflationModelConfig(BaseModel):
    """Ornstein-Uhlenbeck mean-reverting inflation process configuration."""

    mean_reversion_speed: float = Field(
        default=0.1,
        description="Speed of mean reversion (theta) for Ornstein-Uhlenbeck inflation process.",
        json_schema_extra={"min": 0.01, "max": 1.0, "step": 0.01},
    )
    volatility_annual: float = Field(
        default=0.015,
        description="Annual volatility of inflation.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.001,
            "max": 0.20,
            "step": 0.002,
            "unit": "%",
        },
    )
    max_inflation_cap: float = Field(
        default=0.15,
        description="Absolute maximum cap for inflation (e.g., 15%).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.05,
            "max": 0.50,
            "step": 0.01,
            "unit": "%",
        },
    )
    min_deflation_floor: float = Field(
        default=-0.02,
        description="Absolute minimum floor for deflation (e.g., -2%).",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": -0.20,
            "max": 0.05,
            "step": 0.01,
            "unit": "%",
        },
    )


class MonteCarloAssumptions(BaseModel):
    """Monte Carlo multi-path simulation boundaries and embedded stochastic engines."""

    iterations: int = Field(
        ...,
        description="Number of Monte Carlo paths/simulations to run.",
        json_schema_extra={"min": 100, "max": 100000, "step": 500, "unit": "paths"},
    )
    max_months: int = Field(
        ...,
        description="Maximum duration of the Monte Carlo simulation in months.",
        json_schema_extra={"min": 12, "max": 1200, "step": 12, "unit": "months"},
    )
    annual_volatility: float = Field(
        ...,
        description="Assumed annualized standard deviation (volatility) of returns.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": 0.01,
            "max": 0.60,
            "step": 0.01,
            "unit": "%",
        },
    )
    real_return_floor: float = Field(
        ...,
        description="Absolute minimum annualized real return applied during forecasting.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": -0.10,
            "max": 0.20,
            "step": 0.005,
            "unit": "%",
        },
    )
    sorr_cagr_window_months: int = Field(
        default=60,
        description="Months window used to evaluate Sequence of Returns Risk (SORR) CAGR.",
        json_schema_extra={"min": 12, "max": 120, "step": 6, "unit": "months"},
    )
    desired_target_age: int = Field(
        ...,
        description="Desired target age for FIRE calculations.",
        json_schema_extra={"min": 30, "max": 110, "step": 1, "unit": "years"},
    )
    date_of_birth: str = Field(
        ...,
        description="Date of birth in YYYY-MM-DD format.",
        json_schema_extra={"ui_widget": "text", "placeholder": "YYYY-MM-DD"},
    )
    markov_regime: MarkovRegimeConfig = Field(default_factory=MarkovRegimeConfig)
    human_capital: HumanCapitalConfig = Field(default_factory=HumanCapitalConfig)
    glide_path: GlidePathConfig = Field(default_factory=GlidePathConfig)
    jump_diffusion: JumpDiffusionConfig = Field(default_factory=JumpDiffusionConfig)
    guyton_klinger: GuytonKlingerConfig = Field(default_factory=GuytonKlingerConfig)
    inflation_model: InflationModelConfig = Field(default_factory=InflationModelConfig)


class CMAAssumptions(BaseModel):
    """Capital Market Assumptions (CMA) for long-term real returns and tail risk."""

    expected_real_return: float = Field(
        0.05,
        description="Expected real return for long-term forecasting.",
        json_schema_extra={
            "ui_widget": "percentage",
            "min": -0.05,
            "max": 0.20,
            "step": 0.005,
            "unit": "%",
        },
    )
    fat_tail_multiplier: float = Field(
        1.2,
        description="Multiplier to adjust normal volatility for fat tails.",
        json_schema_extra={"min": 1.0, "max": 3.0, "step": 0.1},
    )


class AssumptionsRules(BaseModel):
    """Root configuration grouping macro, FIRE, Monte Carlo, tax, and CMA rules."""

    macro: MacroAssumptions = Field(...)
    fire: FireAssumptions = Field(...)
    monte_carlo: MonteCarloAssumptions = Field(...)
    tax: TaxAssumptions = Field(...)
    cma: CMAAssumptions = Field(
        default_factory=lambda: CMAAssumptions(expected_real_return=0.05, fat_tail_multiplier=1.2)
    )
    target_allocations: dict[str, float] = Field(
        default_factory=dict,
        description="Target portfolio asset class weights summing to 1.0 (e.g. Stocks, ETFs, Mutual Funds).",
        json_schema_extra={"ui_widget": "key_value_dict"},
    )
