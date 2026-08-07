import os
import tomllib

from pydantic import BaseModel, Field


class ActiveIncomeRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class DividendIncomeRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class InterestIncomeRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class IncomeRules(BaseModel):
    active: ActiveIncomeRules = Field(default_factory=ActiveIncomeRules)
    dividends: DividendIncomeRules = Field(default_factory=DividendIncomeRules)
    interest: InterestIncomeRules = Field(default_factory=InterestIncomeRules)


class CoreExpenseRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class ExpenseRules(BaseModel):
    core: CoreExpenseRules = Field(default_factory=CoreExpenseRules)


class IncomeAllocationRules(BaseModel):
    core_expense_pct: float = Field(
        default=0.40,
        description="Max % of smoothed income allocated to core/fixed expenses (40% default).",
    )
    non_core_expense_pct: float = Field(
        default=0.20,
        description="Max % of smoothed income allocated to non-core/discretionary expenses (20% default).",
    )
    investment_pct: float = Field(
        default=0.30,
        description="Minimum % of smoothed income to invest/save via net transfers (30% default).",
    )


class BudgetAlerts(BaseModel):
    overspend_alert_threshold: float = Field(
        default=0.05,
        description="Fractional overage above budget target that triggers Is_Overspent flags (5% default).",
    )
    emergency_fund_target_months: int = Field(
        default=6,
        description="Target number of months of core expenses to hold as emergency fund.",
    )


class BudgetSmoothing(BaseModel):
    income_smoothing_months: int = Field(
        default=3,
        description="Number of trailing months used for recency-weighted income smoothing.",
    )


class BudgetRules(BaseModel):
    income_allocation: IncomeAllocationRules = Field(default=IncomeAllocationRules())
    alerts: BudgetAlerts = Field(default=BudgetAlerts())
    smoothing: BudgetSmoothing = Field(default=BudgetSmoothing())


class IlliquidAssetRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class AssetRules(BaseModel):
    illiquid: IlliquidAssetRules = Field(default_factory=IlliquidAssetRules)


class InvestmentInstrumentRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class MacroAssumptions(BaseModel):
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


class FireAssumptions(BaseModel):
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


class MarkovRegimeConfig(BaseModel):
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


class HumanCapitalConfig(BaseModel):
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


class GlidePathConfig(BaseModel):
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


class JumpDiffusionConfig(BaseModel):
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


class GuytonKlingerConfig(BaseModel):
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
    mean_reversion_speed: float = Field(
        default=0.1,
        description="Speed of mean reversion (theta) for Ornstein-Uhlenbeck inflation process.",
    )
    volatility_annual: float = Field(default=0.015, description="Annual volatility of inflation.")
    max_inflation_cap: float = Field(
        default=0.15, description="Absolute maximum cap for inflation (e.g., 15%)."
    )


class MonteCarloAssumptions(BaseModel):
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


class TaxRates(BaseModel):
    equity_ltcg: float = Field(0.125, description="LTCG tax rate for equity.")
    equity_stcg: float = Field(0.20, description="STCG tax rate for equity.")
    debt_ltcg: float = Field(0.20, description="LTCG tax rate for debt.")
    debt_stcg: float = Field(0.30, description="STCG tax rate for debt.")
    gold_ltcg: float = Field(0.20, description="LTCG tax rate for gold.")
    gold_stcg: float = Field(0.30, description="STCG tax rate for gold.")


class TaxAssumptions(BaseModel):
    debt_mf_cutoff_date: str = Field(
        ..., description="Date before which debt mutual funds have indexation benefits."
    )
    harvest_wait_days_threshold: int = Field(
        ...,
        description="Minimum days to wait before re-buying a harvested instrument to avoid wash-sale rules.",
    )
    ltcg_thresholds: dict[str, int] = Field(
        ...,
        description="Holding period thresholds in days for Long Term Capital Gains across asset classes.",
    )
    fallback_equity_ltcg_exemption: float = Field(
        ..., description="Annual tax-free exemption limit for equity Long Term Capital Gains."
    )
    rates: TaxRates = Field(
        default_factory=lambda: TaxRates(
            equity_ltcg=0.125,
            equity_stcg=0.20,
            debt_ltcg=0.20,
            debt_stcg=0.30,
            gold_ltcg=0.20,
            gold_stcg=0.30,
        )
    )


class CMAAssumptions(BaseModel):
    expected_real_return: float = Field(
        0.05, description="Expected real return for long-term forecasting."
    )
    fat_tail_multiplier: float = Field(
        1.2, description="Multiplier to adjust normal volatility for fat tails."
    )


class AssumptionsRules(BaseModel):
    macro: MacroAssumptions = Field(...)
    fire: FireAssumptions = Field(...)
    monte_carlo: MonteCarloAssumptions = Field(...)
    tax: TaxAssumptions = Field(...)
    cma: CMAAssumptions = Field(
        default_factory=lambda: CMAAssumptions(expected_real_return=0.05, fat_tail_multiplier=1.2)
    )
    target_allocations: dict[str, float] = Field(default_factory=dict)


class FinancialRules(BaseModel):
    income: IncomeRules = Field(default_factory=lambda: IncomeRules())
    expense: ExpenseRules = Field(default_factory=lambda: ExpenseRules())
    assets: AssetRules = Field(default_factory=lambda: AssetRules())
    investments: dict[str, InvestmentInstrumentRules] = Field(default_factory=dict)
    assumptions: AssumptionsRules = Field(...)
    budget: BudgetRules = Field(default_factory=BudgetRules)

    @classmethod
    def from_toml(cls, filepath: str) -> "FinancialRules":
        if not filepath or not os.path.exists(filepath):
            raise FileNotFoundError(f"Financial rules config not found at {filepath}")

        with open(filepath, "rb") as f:
            data = tomllib.load(f)
            return cls(**data)

    def export_to_db_records(self) -> list[dict]:
        """Flattens the rules into a list of records for database auditing."""
        records = []

        # Income Rules
        for cat_id in self.income.active.category_ids:
            records.append(
                {
                    "Rule_Domain": "Income",
                    "Rule_Type": "Active",
                    "Target_Level": "Category",
                    "Target_ID": cat_id,
                }
            )
        for sub_id in self.income.active.sub_category_ids:
            records.append(
                {
                    "Rule_Domain": "Income",
                    "Rule_Type": "Active",
                    "Target_Level": "Subcategory",
                    "Target_ID": sub_id,
                }
            )

        for cat_id in self.income.dividends.category_ids:
            records.append(
                {
                    "Rule_Domain": "Income",
                    "Rule_Type": "Dividends",
                    "Target_Level": "Category",
                    "Target_ID": cat_id,
                }
            )
        for sub_id in self.income.dividends.sub_category_ids:
            records.append(
                {
                    "Rule_Domain": "Income",
                    "Rule_Type": "Dividends",
                    "Target_Level": "Subcategory",
                    "Target_ID": sub_id,
                }
            )

        for cat_id in self.income.interest.category_ids:
            records.append(
                {
                    "Rule_Domain": "Income",
                    "Rule_Type": "Interest",
                    "Target_Level": "Category",
                    "Target_ID": cat_id,
                }
            )
        for sub_id in self.income.interest.sub_category_ids:
            records.append(
                {
                    "Rule_Domain": "Income",
                    "Rule_Type": "Interest",
                    "Target_Level": "Subcategory",
                    "Target_ID": sub_id,
                }
            )

        # Expense Rules
        for cat_id in self.expense.core.category_ids:
            records.append(
                {
                    "Rule_Domain": "Expense",
                    "Rule_Type": "Core",
                    "Target_Level": "Category",
                    "Target_ID": cat_id,
                }
            )
        for sub_id in self.expense.core.sub_category_ids:
            records.append(
                {
                    "Rule_Domain": "Expense",
                    "Rule_Type": "Core",
                    "Target_Level": "Subcategory",
                    "Target_ID": sub_id,
                }
            )

        # Asset Rules
        for cat_id in self.assets.illiquid.category_ids:
            records.append(
                {
                    "Rule_Domain": "Asset",
                    "Rule_Type": "Illiquid",
                    "Target_Level": "Category",
                    "Target_ID": cat_id,
                }
            )
        for sub_id in self.assets.illiquid.sub_category_ids:
            records.append(
                {
                    "Rule_Domain": "Asset",
                    "Rule_Type": "Illiquid",
                    "Target_Level": "Subcategory",
                    "Target_ID": sub_id,
                }
            )

        # Investment Rules
        for instr_name, instr_rules in self.investments.items():
            for cat_id in instr_rules.category_ids:
                records.append(
                    {
                        "Rule_Domain": "Investment",
                        "Rule_Type": instr_name,
                        "Target_Level": "Category",
                        "Target_ID": cat_id,
                    }
                )
            for sub_id in instr_rules.sub_category_ids:
                records.append(
                    {
                        "Rule_Domain": "Investment",
                        "Rule_Type": instr_name,
                        "Target_Level": "Subcategory",
                        "Target_ID": sub_id,
                    }
                )

        # Assumptions Audit Records
        a = self.assumptions
        for key, value in {
            "default_trading_days": a.macro.default_trading_days,
            "fallback_inflation_rate": a.macro.fallback_inflation_rate,
            "fallback_risk_free_rate": a.macro.fallback_risk_free_rate,
        }.items():
            records.append(
                {
                    "Rule_Domain": "Assumption",
                    "Rule_Type": "Macro",
                    "Target_Level": key,
                    "Target_ID": str(value),
                }
            )

        for key, value in {
            "swr_multiplier": a.fire.swr_multiplier,
            "coast_fi_real_return": a.fire.coast_fi_real_return,
            "coast_fi_years": a.fire.coast_fi_years,
            "lean_fi_ratio": a.fire.lean_fi_ratio,
            "fallback_trailing_return": a.fire.fallback_trailing_return,
        }.items():
            records.append(
                {
                    "Rule_Domain": "Assumption",
                    "Rule_Type": "FIRE",
                    "Target_Level": key,
                    "Target_ID": str(value),
                }
            )

        for key, value in {
            "iterations": a.monte_carlo.iterations,
            "max_months": a.monte_carlo.max_months,
            "annual_volatility": a.monte_carlo.annual_volatility,
            "real_return_floor": a.monte_carlo.real_return_floor,
        }.items():
            records.append(
                {
                    "Rule_Domain": "Assumption",
                    "Rule_Type": "MonteCarlo",
                    "Target_Level": key,
                    "Target_ID": str(value),
                }
            )

        for key, value in {
            "debt_mf_cutoff_date": a.tax.debt_mf_cutoff_date,
            "harvest_wait_days_threshold": a.tax.harvest_wait_days_threshold,
            "fallback_equity_ltcg_exemption": a.tax.fallback_equity_ltcg_exemption,
        }.items():
            records.append(
                {
                    "Rule_Domain": "Assumption",
                    "Rule_Type": "Tax",
                    "Target_Level": key,
                    "Target_ID": str(value),
                }
            )

        return records
