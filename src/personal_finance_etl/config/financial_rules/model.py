"""Authoritative FinancialRules configuration model.

Owns
----
- Root FinancialRules configuration model composed of capability-scoped policies.
- TOML deserialization and plan-driven validation.
- Dimension validation for investment exclusions.
- Export flattening for database audit and rule governance tables.

Does not own
-------------
- Specific domain rule definitions (owned by child modules in config.financial_rules).
- System-wide environment or file hash configuration (owned by config.settings).
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from typing import Self, cast

import polars as pl
from pydantic import BaseModel, Field

from personal_finance_etl.config.financial_rules.fire import (
    AssumptionsRules,
    FireCapabilityRules,
)
from personal_finance_etl.config.financial_rules.household import (
    AssetRules,
    BudgetRules,
    ExpenseRules,
    HouseholdCapabilityRules,
    IncomeRules,
    WealthCapabilityRules,
)
from personal_finance_etl.config.financial_rules.investments import (
    InvestmentsCapabilityRules,
    PortfolioManagementRules,
)
from personal_finance_etl.config.financial_rules.tax import (
    TaxCapabilityRules,
)
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.diagnostics import DiagnosticIssue, DiagnosticSeverity
from personal_finance_etl.contracts.execution_plan import ExecutionPlan

__all__ = ["BenchmarkCapabilityRules", "FinancialRules"]


class BenchmarkCapabilityRules(BaseModel):
    """Configuration rules for market benchmark enrichment."""

    default_benchmark_index: str = Field(
        default="NIFTY 50",
        description="Primary benchmark index identifier for relative alpha calculation.",
    )
    fallback_risk_free_rate: float = Field(
        default=0.06,
        description="Annualized risk-free rate used for Sharpe ratio calculation (e.g. 0.06 for 6%).",
    )
    track_benchmark_alpha: bool = Field(
        default=True,
        description="Whether to compute alpha and beta tracking metrics against the benchmark index.",
    )


def _map_rule_domain(first_key: str) -> str:
    """Map the root configuration key to a sanitized rule domain string."""
    domain = first_key.capitalize()
    if domain.endswith("s") and domain != "Assumptions":
        domain = domain[:-1]
    if domain == "Assumptions":
        domain = "Assumption"
    return domain


def _map_rule_type(path: list[str]) -> str:
    """Map the second path component to a formatted rule type string."""
    if len(path) <= 1:
        return "Global"
    raw_rule = str(path[1])
    if raw_rule.lower() in ("cma", "fire", "mf", "etf", "roi"):
        return raw_rule.upper()
    return raw_rule.replace("_", " ").title().replace(" ", "")


def _map_target_level(last_key: str) -> str:
    """Map the deepest key in the path to a target hierarchy level."""
    if last_key == "category_ids":
        return "Category"
    if last_key == "sub_category_ids":
        return "Subcategory"
    return last_key


def _format_db_record(path: list[str], val: object) -> dict[str, str] | None:
    """Format a single leaf property into a database audit record."""
    if not path or val is None:
        return None
    return {
        "Rule_Domain": _map_rule_domain(path[0]),
        "Rule_Type": _map_rule_type(path),
        "Target_Level": _map_target_level(str(path[-1])),
        "Target_ID": str(val),
    }


def _flatten_data_to_records(node: object, path: list[str], records: list[dict[str, str]]) -> None:
    """Recursively traverse a dictionary or list to extract leaf audit records."""
    if isinstance(node, dict):
        dict_node = cast("dict[str, object]", node)
        for k, v in dict_node.items():
            _flatten_data_to_records(v, path + [k], records)
    elif isinstance(node, list):
        list_node = cast("list[object]", node)
        for item in list_node:
            record = _format_db_record(path, item)
            if record is not None:
                records.append(record)
    else:
        record = _format_db_record(path, node)
        if record is not None:
            records.append(record)


class FinancialRules(BaseModel):
    """Root configuration composed of capability-scoped domain policy models."""

    household: HouseholdCapabilityRules = Field(default_factory=HouseholdCapabilityRules)
    wealth: WealthCapabilityRules = Field(default_factory=WealthCapabilityRules)
    investments: InvestmentsCapabilityRules = Field(default_factory=InvestmentsCapabilityRules)
    tax: TaxCapabilityRules | None = None
    fire: FireCapabilityRules | None = None
    benchmark: BenchmarkCapabilityRules = Field(default_factory=BenchmarkCapabilityRules)

    # Pure convenience properties for internal domain calculation access
    @property
    def income(self) -> IncomeRules:
        """Household income classification rules."""
        return self.household.income

    @property
    def expense(self) -> ExpenseRules:
        """Household expense classification rules."""
        return self.household.expense

    @property
    def budget(self) -> BudgetRules:
        """Household budget allocation and smoothing rules."""
        return self.household.budget

    @property
    def assets(self) -> AssetRules:
        """Wealth asset liquidity classification rules."""
        return self.wealth.assets

    @property
    def portfolio_management(self) -> PortfolioManagementRules:
        """Investment portfolio drift and rebalance rules."""
        return self.investments.portfolio_management

    @property
    def DEFAULT_CURRENCY_ID(self) -> str:
        """Base currency identifier."""
        return self.investments.default_currency_id

    @property
    def MF_SCHEME_MAPPINGS(self) -> dict[str, str]:
        """Mutual fund scheme name normalization mappings."""
        return self.investments.mf_scheme_mappings

    @property
    def assumptions(self) -> AssumptionsRules:
        """Domain view projection assembling statutory tax policies and simulation parameters for calculation engines."""
        if self.fire is None or self.tax is None:
            raise AttributeError(
                "Capability rules [tax] and [fire] must be configured to access assumptions."
            )
        return AssumptionsRules.model_construct(
            macro=self.fire.macro,
            fire=self.fire.fire,
            monte_carlo=self.fire.monte_carlo,
            tax=self.tax,
            cma=self.fire.cma,
            target_allocations=self.fire.target_allocations,
        )

    def validate_against_plan(self, plan: ExecutionPlan) -> list[DiagnosticIssue]:
        """Validate that all capabilities enabled in the execution plan have configured rules."""
        issues: list[DiagnosticIssue] = []
        if CapabilityId.TAX in plan.active_capabilities:
            if self.tax is None:
                issues.append(
                    DiagnosticIssue(
                        category="RULES",
                        severity=DiagnosticSeverity.ERROR,
                        location="financial_rules.toml",
                        field="tax",
                        message="Active capability 'tax' requires a configured [tax] section in financial rules.",
                        remediation="Add a valid [tax] section with rates and statutory parameters.",
                    )
                )
        if CapabilityId.FIRE in plan.active_capabilities:
            if self.fire is None:
                issues.append(
                    DiagnosticIssue(
                        category="RULES",
                        severity=DiagnosticSeverity.ERROR,
                        location="financial_rules.toml",
                        field="fire",
                        message="Active capability 'fire' requires a configured [fire] section in financial rules.",
                        remediation="Add a valid [fire] section with macro, fire, and monte_carlo parameters.",
                    )
                )
        return issues

    def validate_investment_exclusion_uids(
        self, df_subcategory: pl.DataFrame | pl.LazyFrame
    ) -> None:
        """Validate configured investment exclusions against the actual subcategory dimension."""
        if self.tax is None:
            return

        if isinstance(df_subcategory, pl.LazyFrame):
            # Materialization Boundary: VALIDATION_DIAGNOSTIC
            # Materialize subcategory dimension to validate configured investment exclusions
            df_materialized = df_subcategory.collect()
        else:
            df_materialized = df_subcategory

        if "UID" not in df_materialized.columns:
            raise ValueError(
                "Income subcategory dimension must contain UID to validate investment exclusions."
            )

        configured = set(self.tax.investment_exclusions.stcg_sub_cat_ids)
        configured.update(self.tax.investment_exclusions.ltcg_sub_cat_ids)
        if not configured:
            return

        available = {
            str(uid).strip()
            for uid in df_materialized.get_column("UID").drop_nulls().to_list()
            if str(uid).strip()
        }
        unknown = sorted(configured - available)
        if unknown:
            raise ValueError(
                "Configured STCG/LTCG investment exclusion UID(s) do not exist in "
                f"silver.wealth_income_subcategory: {unknown}"
            )

    @classmethod
    def from_toml(cls, filepath: str | os.PathLike[str]) -> Self:
        """Load and instantiate FinancialRules from a TOML configuration file."""
        path_str = os.fspath(filepath)
        if not path_str or not os.path.exists(path_str):
            raise FileNotFoundError(f"Financial rules config not found at {path_str}")

        with open(path_str, "rb") as f:
            data = tomllib.load(f)

        # Strict capability-scoping enforcement: Disallow non-capability top-level root keys
        non_capability_keys = {
            "income",
            "expense",
            "assumptions",
            "assets",
            "DEFAULT_CURRENCY_ID",
            "MF_SCHEME_MAPPINGS",
        }
        found_invalid = non_capability_keys.intersection(data.keys())
        if found_invalid:
            raise ValueError(
                f"Non-capability root keys {sorted(found_invalid)} are forbidden. "
                "Financial rules must strictly use capability namespaces: "
                "[household], [wealth], [investments], [tax], [fire], [benchmark]."
            )

        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Self:
        """Instantiate FinancialRules directly from a raw configuration dictionary."""
        # Strict capability-scoping enforcement: Disallow non-capability top-level root keys
        non_capability_keys = {
            "income",
            "expense",
            "assumptions",
            "assets",
            "DEFAULT_CURRENCY_ID",
            "MF_SCHEME_MAPPINGS",
        }
        found_invalid = non_capability_keys.intersection(data.keys())
        if found_invalid:
            raise ValueError(
                f"Non-capability root keys {sorted(found_invalid)} are forbidden. "
                "Financial rules must strictly use capability namespaces: "
                "[household], [wealth], [investments], [tax], [fire], [benchmark]."
            )
        return cls.model_validate(data)

    def export_to_db_records(self) -> list[dict[str, str]]:
        """Flatten the rules dynamically into records for database auditing."""
        records: list[dict[str, str]] = []
        data = self.model_dump()
        _flatten_data_to_records(data, [], records)
        return records
