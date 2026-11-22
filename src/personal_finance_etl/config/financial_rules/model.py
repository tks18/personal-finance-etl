"""Authoritative FinancialRules configuration model.

Owns
----
- Root FinancialRules configuration model composed of domain policies.
- TOML deserialization and dimension validation for investment exclusions.
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

from personal_finance_etl.config.financial_rules.fire import AssumptionsRules
from personal_finance_etl.config.financial_rules.household import (
    AssetRules,
    BudgetRules,
    ExpenseRules,
    IncomeRules,
)
from personal_finance_etl.config.financial_rules.investments import (
    InvestmentInstrumentRules,
    PortfolioManagementRules,
)

__all__ = ["FinancialRules"]


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
    """Root configuration composed of domain policies, assumptions, and audit rules."""

    income: IncomeRules = Field(default_factory=IncomeRules)
    expense: ExpenseRules = Field(default_factory=ExpenseRules)
    assets: AssetRules = Field(default_factory=AssetRules)
    investments: dict[str, InvestmentInstrumentRules] = Field(default_factory=dict)
    assumptions: AssumptionsRules = Field(...)
    budget: BudgetRules = Field(default_factory=BudgetRules)
    portfolio_management: PortfolioManagementRules = Field(default_factory=PortfolioManagementRules)

    # Transactional rules
    DEFAULT_CURRENCY_ID: str = "INR_INR"
    MF_SCHEME_MAPPINGS: dict[str, str] = Field(default_factory=dict)

    def validate_investment_exclusion_uids(
        self, df_subcategory: pl.DataFrame | pl.LazyFrame
    ) -> None:
        """Validate configured investment exclusions against the actual subcategory dimension.

        Pydantic can validate duplicate/overlapping configuration values, but only the
        materialized dimension can establish whether a UID exists in the current source data.
        """
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

        configured = set(self.assumptions.tax.investment_exclusions.stcg_sub_cat_ids)
        configured.update(self.assumptions.tax.investment_exclusions.ltcg_sub_cat_ids)
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
                f"silver.d_Income_Subcategory: {unknown}"
            )

    @classmethod
    def from_toml(cls, filepath: str | os.PathLike[str]) -> Self:
        """Load and instantiate FinancialRules from a TOML configuration file."""
        path_str = os.fspath(filepath)
        if not path_str or not os.path.exists(path_str):
            raise FileNotFoundError(f"Financial rules config not found at {path_str}")

        with open(path_str, "rb") as f:
            data = tomllib.load(f)
            return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Self:
        """Instantiate FinancialRules directly from a raw configuration dictionary."""
        return cls.model_validate(data)

    def export_to_db_records(self) -> list[dict[str, str]]:
        """Flatten the rules dynamically into records for database auditing.

        Automatically scales to handle new nested parameters added to the schema.
        """
        records: list[dict[str, str]] = []
        data = self.model_dump()
        _flatten_data_to_records(data, [], records)
        return records
