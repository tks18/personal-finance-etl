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

from typing import Self

from pydantic import BaseModel, Field, model_validator

from personal_finance_etl.config.financial_rules.tax import TaxAssumptions

__all__ = [
    "AssumptionsRules",
    "CMAAssumptions",
    "FireAssumptions",
    "FireCapabilityRules",
    "GlidePathConfig",
    "GuytonKlingerConfig",
    "HumanCapitalConfig",
    "InflationModelConfig",
    "JumpDiffusionConfig",
    "MacroAssumptions",
    "MarkovRegimeConfig",
    "MonteCarloAssumptions",
]


class MacroAssumptions(BaseModel):
    """Baseline macroeconomic parameter configuration for annualization and fallbacks."""

    default_trading_days: float = Field(
        ...,
        description="Default number of trading days in a year for annualized volatility calculations.",
    )
    fallback_inflation_rate: float = Field(
        ...,
        description="Fallback annualized inflation rate if historical macro data is unavailable.",
    )
    fallback_risk_free_rate: float = Field(
        ...,
        description="Fallback annualized risk-free rate if historical macro data is unavailable.",
    )
    fallback_ordinary_income_rate: float = Field(
        default=0.30,
        description="Fallback ordinary income tax rate (marginal slab) if not found in macro table.",
    )


class FireAssumptions(BaseModel):
    """Financial Independence and Safe Withdrawal Rate forecasting rules."""

    swr_multiplier: float = Field(
        ..., description="Safe Withdrawal Rate multiplier (e.g., 25.0 for 4% rule)."
    )
    coast_fi_real_return: float = Field(
        ..., description="Assumed real (inflation-adjusted) return for Coast FI calculations."
    )
    coast_fi_years: int = Field(
        ..., description="Number of years to coast (compound) for Coast FI."
    )
    lean_fi_ratio: float = Field(
        ..., description="Ratio of Target FI considered sufficient for Lean FI."
    )
    fallback_trailing_return: float = Field(
        ...,
        description="Fallback nominal return to use for FIRE forecasting if historical returns are unavailable.",
    )

    cape_swr_floor: float = Field(..., description="Floor SWR during severe drawdown.")
    cape_swr_ceiling: float = Field(..., description="Ceiling SWR during moderate drawdown.")
    cape_swr_base: float = Field(..., description="Base SWR during normal markets.")
    human_capital_max_age: float = Field(
        ..., description="Maximum age until which you expect to be healthy and working."
    )
    human_capital_discount_rate: float = Field(..., description="Discount rate for human capital.")

    @model_validator(mode="after")
    def validate_swr(self) -> Self:
        """Validate that SWR multiplier is strictly positive."""
        if self.swr_multiplier <= 0.0:
            raise ValueError(
                f"SWR multiplier must be strictly positive (> 0.0), got {self.swr_multiplier}."
            )
        return self


class MarkovRegimeConfig(BaseModel):
    """Three-state Markov regime switching parameters (Bull, Bear, Stagflation)."""

    transition_matrix: list[list[float]] = Field(
        default=[
            [0.90, 0.08, 0.02],
            [0.15, 0.80, 0.05],
            [0.10, 0.15, 0.75],
        ],
        description="3x3 Matrix for probabilities of transitioning between Bull, Bear, and Stagflation states.",
    )
    state_bull: tuple[float, float, float] = Field(
        default=(0.10, 0.12, 0.04),
        description="Bull Market parameters: (drift, volatility, inflation target)",
    )
    state_bear: tuple[float, float, float] = Field(
        default=(-0.15, 0.25, 0.02),
        description="Bear Market parameters: (drift, volatility, inflation target)",
    )
    state_stag: tuple[float, float, float] = Field(
        default=(-0.05, 0.18, 0.08),
        description="Stagflation parameters: (drift, volatility, inflation target)",
    )

    @model_validator(mode="after")
    def validate_stochastic_matrix(self) -> Self:
        """Validate bounded probabilities and stochastic matrix row normalization."""
        for i, row in enumerate(self.transition_matrix):
            for p in row:
                if not 0.0 <= p <= 1.0:
                    raise ValueError(
                        f"Markov transition probability {p} must be bounded between 0.0 and 1.0."
                    )
            row_sum = sum(row)
            if abs(row_sum - 1.0) > 1e-4:
                raise ValueError(
                    f"Markov transition matrix row {i} must sum strictly to 1.0 (got {row_sum:.4f})."
                )
        return self


class HumanCapitalConfig(BaseModel):
    """Human capital income shock probabilities and severance coverage parameters."""

    shock_probability: float = Field(
        default=0.20,
        description="Probability of an income shock (job loss, zero bonus) when in Bear or Stagflation states.",
    )
    shock_duration_min: int = Field(
        default=6, description="Minimum duration (in months) of the income shock."
    )
    shock_duration_max: int = Field(
        default=12, description="Maximum duration (in months) of the income shock."
    )
    unemployment_benefit_coverage_pct: float = Field(
        default=0.0,
        description="Percentage of core expenses covered by unemployment benefits or severance during a shock.",
    )

    @model_validator(mode="after")
    def validate_probabilities(self) -> Self:
        """Validate probability bounds for human capital shock."""
        if not 0.0 <= self.shock_probability <= 1.0:
            raise ValueError(
                "Human capital shock_probability must be bounded between 0.0 and 1.0 "
                f"(got {self.shock_probability})."
            )
        return self


class GlidePathConfig(BaseModel):
    """Retirement asset allocation glide path, de-risking, and debt buffer rules."""

    derisk_start_months_prior: int = Field(
        default=60,
        description="Months prior to the FI target date to begin de-risking the portfolio.",
    )
    post_fi_re_risk_months: int = Field(
        default=120,
        description="Months after reaching FI to slowly re-risk the portfolio back to base.",
    )
    base_equity_weight: float = Field(
        default=0.70, description="Base/maximum equity allocation weight (e.g., 70%)."
    )
    fi_target_equity_weight: float = Field(
        default=0.40,
        description="Target minimum equity allocation weight upon reaching FI (e.g., 40%).",
    )
    debt_real_return: float = Field(
        default=0.02,
        description="Expected real return for the non-equity (debt) portion of the glide path.",
    )
    debt_volatility: float = Field(
        default=0.04,
        description="Expected volatility for the non-equity (debt) portion of the glide path.",
    )
    dynamic_debt_drawdown_first: bool = Field(
        default=False,
        description="If True, during decumulation down-months, withdrawals are taken from debt, bypassing equity liquidation.",
    )


class JumpDiffusionConfig(BaseModel):
    """Black Swan jump diffusion crash parameters and investment fee drag."""

    jump_probability_annual: float = Field(
        default=0.05, description="Annual probability of a Black Swan market crash (e.g., 5%)."
    )
    jump_magnitude: float = Field(
        default=-0.20, description="The magnitude of the crash when a jump occurs (e.g., -20%)."
    )
    expense_ratio_drag: float = Field(
        default=0.005,
        description="Annual portfolio expense ratio or fee drag deducted from returns (e.g., 50 bps).",
    )

    @model_validator(mode="after")
    def validate_probabilities(self) -> Self:
        """Validate probability bounds for Merton jump diffusion."""
        if not 0.0 <= self.jump_probability_annual <= 1.0:
            raise ValueError(
                "Jump diffusion jump_probability_annual must be bounded between 0.0 and 1.0 "
                f"(got {self.jump_probability_annual})."
            )
        return self


class GuytonKlingerConfig(BaseModel):
    """Guyton-Klinger dynamic withdrawal rules and capital preservation guardrails."""

    withdrawal_upper_threshold: float = Field(
        default=1.2,
        description="Multiplier over initial SWR to trigger a lifestyle cut (e.g., 1.2 for +20%).",
    )
    withdrawal_lower_threshold: float = Field(
        default=0.8,
        description="Multiplier under initial SWR to trigger a lifestyle raise (e.g., 0.8 for -20%).",
    )
    lifestyle_cut_multiplier: float = Field(
        default=0.90,
        description="Multiplier for withdrawal amount when cutting lifestyle (e.g., 0.90 for -10%).",
    )
    lifestyle_raise_multiplier: float = Field(
        default=1.10,
        description="Multiplier for withdrawal amount when raising lifestyle (e.g., 1.10 for +10%).",
    )


class InflationModelConfig(BaseModel):
    """Ornstein-Uhlenbeck mean-reverting inflation process configuration."""

    mean_reversion_speed: float = Field(
        default=0.1,
        description="Speed of mean reversion (theta) for Ornstein-Uhlenbeck inflation process.",
    )
    volatility_annual: float = Field(default=0.015, description="Annual volatility of inflation.")
    max_inflation_cap: float = Field(
        default=0.15, description="Absolute maximum cap for inflation (e.g., 15%)."
    )
    min_deflation_floor: float = Field(
        default=-0.02, description="Absolute minimum floor for deflation (e.g., -2%)."
    )


class MonteCarloAssumptions(BaseModel):
    """Monte Carlo multi-path simulation boundaries and embedded stochastic engines."""

    iterations: int = Field(..., description="Number of Monte Carlo paths/simulations to run.")
    max_months: int = Field(
        ..., description="Maximum duration of the Monte Carlo simulation in months."
    )
    annual_volatility: float = Field(
        ..., description="Assumed annualized standard deviation (volatility) of returns."
    )
    real_return_floor: float = Field(
        ..., description="Absolute minimum annualized real return applied during forecasting."
    )
    sorr_cagr_window_months: int = Field(
        default=60,
        description="Months window used to evaluate Sequence of Returns Risk (SORR) CAGR.",
    )
    desired_target_age: int = Field(..., description="Desired target age for FIRE calculations.")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format.")
    markov_regime: MarkovRegimeConfig = Field(default_factory=MarkovRegimeConfig)
    human_capital: HumanCapitalConfig = Field(default_factory=HumanCapitalConfig)
    glide_path: GlidePathConfig = Field(default_factory=GlidePathConfig)
    jump_diffusion: JumpDiffusionConfig = Field(default_factory=JumpDiffusionConfig)
    guyton_klinger: GuytonKlingerConfig = Field(default_factory=GuytonKlingerConfig)
    inflation_model: InflationModelConfig = Field(default_factory=InflationModelConfig)

    @model_validator(mode="after")
    def validate_numerical_constraints(self) -> Self:
        """Validate Monte Carlo numerical boundaries and volatility constraints."""
        if self.iterations < 100:
            raise ValueError(
                f"Monte Carlo iterations must be at least 100 (got {self.iterations})."
            )
        if self.annual_volatility <= 0.0:
            raise ValueError(
                "Monte Carlo annual_volatility must be strictly positive (> 0.0), "
                f"got {self.annual_volatility}."
            )
        if self.max_months <= 0:
            raise ValueError(
                f"Monte Carlo max_months must be strictly positive (> 0), got {self.max_months}."
            )
        return self


class CMAAssumptions(BaseModel):
    """Capital Market Assumptions (CMA) for long-term real returns and tail risk."""

    expected_real_return: float = Field(
        0.05, description="Expected real return for long-term forecasting."
    )
    fat_tail_multiplier: float = Field(
        1.2, description="Multiplier to adjust normal volatility for fat tails."
    )


class FireCapabilityRules(BaseModel):
    """Configuration rules for macroeconomic, FIRE, and Monte Carlo simulation policies."""

    macro: MacroAssumptions = Field(...)
    fire: FireAssumptions = Field(...)
    monte_carlo: MonteCarloAssumptions = Field(...)
    cma: CMAAssumptions = Field(
        default_factory=lambda: CMAAssumptions(expected_real_return=0.05, fat_tail_multiplier=1.2)
    )
    target_allocations: dict[str, float] = Field(default_factory=dict)


class AssumptionsRules(BaseModel):
    """Root configuration grouping macro, FIRE, Monte Carlo, tax, and CMA rules."""

    macro: MacroAssumptions = Field(...)
    fire: FireAssumptions = Field(...)
    monte_carlo: MonteCarloAssumptions = Field(...)
    tax: TaxAssumptions = Field(...)
    cma: CMAAssumptions = Field(
        default_factory=lambda: CMAAssumptions(expected_real_return=0.05, fat_tail_multiplier=1.2)
    )
    target_allocations: dict[str, float] = Field(default_factory=dict)
