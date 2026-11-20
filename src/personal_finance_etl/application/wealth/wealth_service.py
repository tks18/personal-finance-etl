"""Wealth presentation and analytical engine orchestrator.

Owns
----
- WealthPresentationEngine (WealthService): Coordinates generation of Gold presentation models.
- Execution DAG ordering: Inflation -> Ledger -> Net Worth -> Analytical Builders.
- Imputation and NaN cleanup for Power BI / DuckDB compatibility.

Does not own
-------------
- Raw transaction stage ingestion (owned by domain.household.transforms).
- Simulation mathematical kernels (owned by domain.fire.simulation).
- DuckDB persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl
import polars.selectors as cs

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.observability import (
    EventCode,
    PresentationKind,
)
from personal_finance_etl.domain.common.calculation import CalculationStatus
from personal_finance_etl.domain.fire.deterministic import WealthRiskAnalyticsBuilder
from personal_finance_etl.domain.fire.inflation import InflationBuilder
from personal_finance_etl.domain.household.budget import BudgetForecastBuilder
from personal_finance_etl.domain.household.cashflow import (
    CashflowStatementBuilder,
    MonthlyCashflowSummaryBuilder,
)
from personal_finance_etl.domain.household.expense import SpendAnalyticsBuilder
from personal_finance_etl.domain.household.income import IncomeStreamsBuilder
from personal_finance_etl.domain.household.ledger import LedgerBuilder
from personal_finance_etl.domain.wealth.analytics import InvestmentAnalyticsBuilder
from personal_finance_etl.domain.wealth.net_worth import NetWorthBuilder
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = ["WealthPresentationEngine", "WealthService"]

diagnostics = get_observability_diagnostics(__name__)


class WealthService:
    """Orchestrates presentation and analytical calculation DAG.

    Consumes Silver-tier LazyFrames and produces unified Gold-tier presentation summary tables.
    """

    def __init__(
        self,
        rules: FinancialRules,
        root_seed: str = "default_seed",
        emitter: ObservabilityEmitter | None = None,
        enable_tax: bool = True,
        plan: ExecutionPlan | None = None,
    ) -> None:
        self.rules = rules
        self.root_seed = root_seed
        self.emitter = emitter or get_global_emitter()
        self.plan = plan

        if plan is not None:
            self.is_household_active = plan.is_capability_active(CapabilityId.HOUSEHOLD_CORE)
            self.is_wealth_active = plan.is_capability_active(CapabilityId.WEALTH)
            self.is_fire_active = plan.is_capability_active(CapabilityId.FIRE)
            self.is_investment_active = plan.is_capability_active(
                CapabilityId.INVESTMENT_ACCOUNTING
            )
            self.is_foreign_active = plan.is_capability_active(
                CapabilityId.FOREIGN_ASSET_ENRICHMENT
            )
            self.enable_tax = plan.is_capability_active(CapabilityId.TAX)
        else:
            self.is_household_active = True
            self.is_wealth_active = True
            self.is_fire_active = True
            self.is_investment_active = True
            self.is_foreign_active = True
            self.enable_tax = enable_tax

    def _build_core_models(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]
    ) -> dict[str, pl.LazyFrame] | None:
        """Execute prerequisite foundation models: Inflation, Ledger, and Net Worth."""
        self.emitter.emit_event(
            event_code=EventCode.WEALTH_ENGINE_START,
            message="Building core wealth models (Inflation, Ledger, Net Worth)...",
            presentation_kind=PresentationKind.STEP,
            stage=EngineStage.ANALYZING,
        )
        inflation_res = InflationBuilder(dfs, rules=self.rules).build()
        if not inflation_res:
            return None

        cpi_res = inflation_res.get("cpi_result")
        if cpi_res and cpi_res.status == CalculationStatus.COMPUTATION_ERROR:
            raise RuntimeError(
                f"Inflation computation failed: {cpi_res.reason}. "
                "Aborting presentation DAG to prevent corrupted downstream FIRE state."
            )

        ledger_res = LedgerBuilder(dfs, rules=self.rules).build()
        if not ledger_res:
            return None

        net_worth_res = NetWorthBuilder(
            dfs,
            inflation_res,
            ledger_res,
            self.rules.DEFAULT_CURRENCY_ID,
            is_investment_active=self.is_investment_active,
            is_foreign_active=self.is_foreign_active,
            is_wealth_active=self.is_wealth_active,
        ).build()

        return {
            "lf_months": inflation_res["lf_months"],
            "lf_inflation": inflation_res["lf_inflation"],
            **ledger_res,
            **net_worth_res,
        }

    def _build_presentation_tables(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, pl.LazyFrame],
    ) -> dict[str, pl.LazyFrame]:
        """Execute downstream presentation and analytical model builders."""
        results: dict[str, pl.LazyFrame] = {
            "df_p_tf_wealth_monthly_totals": base_lf["lf_monthly_totals"],
        }

        if self.is_wealth_active:
            results["df_p_tf_net_worth_monthly_summary"] = base_lf["lf_nw_summary"]

        if self.is_household_active:
            results["df_p_tf_category_spend_analytics"] = SpendAnalyticsBuilder(
                dfs, base_lf, rules=self.rules
            ).build()
            results["df_p_tf_income_streams_monthly"] = IncomeStreamsBuilder(
                dfs, base_lf, rules=self.rules
            ).build()
            results["df_p_tf_budget_forecast_monthly"] = BudgetForecastBuilder(
                dfs, base_lf, rules=self.rules
            ).build()
            results["df_p_tf_monthly_cashflow_summary"] = MonthlyCashflowSummaryBuilder(
                dfs, base_lf, rules=self.rules
            ).build()
            results["df_p_tf_cashflow_activity_summary"] = CashflowStatementBuilder(
                dfs, base_lf, rules=self.rules
            ).build()

        if self.is_investment_active:
            results["df_p_tf_investment_analytics"] = InvestmentAnalyticsBuilder(
                dfs, base_lf, rules=self.rules, enable_tax=self.enable_tax
            ).build()

        if self.is_wealth_active:
            if self.is_fire_active:
                iterations = (
                    self.rules.assumptions.monte_carlo.iterations
                    if self.rules.assumptions and self.rules.assumptions.monte_carlo
                    else 1000
                )
                self.emitter.emit_event(
                    event_code=EventCode.FIRE_ENGINE_START,
                    message=f"Starting FIRE Monte Carlo simulation engine ({iterations:,} paths)...",
                    presentation_kind=PresentationKind.STEP,
                    stage=EngineStage.ANALYZING,
                    entity_type="Engine",
                    entity_id="MonteCarlo",
                    rows=iterations,
                )
            wealth_risk_res = WealthRiskAnalyticsBuilder(
                dfs,
                base_lf,
                rules=self.rules,
                root_seed=self.root_seed,
                is_fire_active=self.is_fire_active,
                is_investment_active=self.is_investment_active,
            ).build()
            results.update(wealth_risk_res)
            if self.is_fire_active:
                self.emitter.emit_event(
                    event_code=EventCode.FIRE_ENGINE_COMPLETED,
                    message=f"FIRE Monte Carlo simulations complete — generated {len(wealth_risk_res)} risk models",
                    presentation_kind=PresentationKind.SUCCESS,
                    stage=EngineStage.ANALYZING,
                    entity_type="Engine",
                    entity_id="MonteCarlo",
                    rows=len(wealth_risk_res),
                )
            else:
                self.emitter.emit_event(
                    event_code=EventCode.FIRE_ENGINE_START,
                    message="Capability 'fire' inactive in execution plan. Skipping FIRE simulation matrix.",
                    presentation_kind=PresentationKind.SKIP,
                    stage=EngineStage.ANALYZING,
                    entity_type="Engine",
                    entity_id="MonteCarlo",
                )

        return results

    def run(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]) -> dict[str, pl.LazyFrame]:
        """Execute the presentation DAG across household, wealth, and FIRE builders.

        Parameters
        ----------
        dfs : Mapping[str, pl.DataFrame | pl.LazyFrame]
            Collection of Silver-tier tables and dimensions.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary of computed presentation LazyFrames with NaN values cleaned to nulls.
        """
        diagnostics.debug("Starting Wealth Engine presentation layer builds...")
        diagnostics.debug("Imputing missing data (NaN) with 0.0 for BI Engine compatibility...")

        base_lf = self._build_core_models(dfs)
        if base_lf is None:
            return {}

        results = self._build_presentation_tables(dfs, base_lf)
        diagnostics.debug("  -> Built %d BI presentation tables in DAG.", len(results))
        self.emitter.emit_event(
            event_code=EventCode.WEALTH_ENGINE_COMPLETED,
            message=f"Wealth presentation models assembled ({len(results)} tables)",
            presentation_kind=PresentationKind.SUCCESS,
            stage=EngineStage.ANALYZING,
            rows=len(results),
        )

        return {key: lf.with_columns(cs.float().fill_nan(None)) for key, lf in results.items()}


WealthPresentationEngine = WealthService
