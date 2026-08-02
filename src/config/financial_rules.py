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


class InvestmentInstrumentRules(BaseModel):
    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class MacroAssumptions(BaseModel):
    cpi_base_index: float = Field(default=151.4)
    default_trading_days: float = Field(default=252.0)


class FireAssumptions(BaseModel):
    swr_multiplier: float = Field(default=25.0)
    coast_fi_real_return: float = Field(default=0.05)
    coast_fi_years: int = Field(default=10)
    lean_fi_ratio: float = Field(default=0.7)
    fallback_trailing_return: float = Field(default=0.12)


class MonteCarloAssumptions(BaseModel):
    iterations: int = Field(default=1000)
    max_months: int = Field(default=480)
    annual_volatility: float = Field(default=0.15)
    real_return_floor: float = Field(default=0.01)


class TaxAssumptions(BaseModel):
    debt_mf_cutoff_date: str = Field(default="2023-04-01")
    harvest_wait_days_threshold: int = Field(default=90)
    ltcg_thresholds: dict[str, int] = Field(
        default_factory=lambda: {
            "equity_listed": 365,
            "equity_unlisted": 730,
            "debt_mf": 1095,
            "debt_other": 1095,
            "debt_": 1095,
            "gold_mf": 730,
            "gold_": 365,
            "sgb_mf": 730,
            "sgb_": 365,
            "silver_mf": 730,
            "silver_": 365,
        }
    )


class AssumptionsRules(BaseModel):
    macro: MacroAssumptions = Field(default_factory=MacroAssumptions)
    fire: FireAssumptions = Field(default_factory=FireAssumptions)
    monte_carlo: MonteCarloAssumptions = Field(default_factory=MonteCarloAssumptions)
    tax: TaxAssumptions = Field(default_factory=TaxAssumptions)


class FinancialRules(BaseModel):
    income: IncomeRules = Field(default_factory=IncomeRules)
    expense: ExpenseRules = Field(default_factory=ExpenseRules)
    investments: dict[str, InvestmentInstrumentRules] = Field(default_factory=dict)
    assumptions: AssumptionsRules = Field(default_factory=AssumptionsRules)

    @classmethod
    def from_toml(cls, filepath: str) -> "FinancialRules":
        if not filepath or not os.path.exists(filepath):
            return cls()

        with open(filepath, "rb") as f:
            try:
                data = tomllib.load(f)
                if not data:
                    return cls()
                return cls(**data)
            except Exception as e:
                # If parsing fails, return empty config but raise/log appropriately in a real app
                print(f"Failed to parse Financial Rules TOML: {e}")
                return cls()

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
            "cpi_base_index": a.macro.cpi_base_index,
            "default_trading_days": a.macro.default_trading_days,
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
