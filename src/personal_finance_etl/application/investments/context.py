"""Run-scoped analytics coordination context and context initialization.

Owns
----
- RunContext: Container holding immutable input DataFrames, FY macro parameters,
  date intervals, and FX rate providers for a single quant execution run.
- AnalyticsContextManager: Validates and initializes RunContext from DataFrames or files,
  identifying unique actionable ISINs across purchases, sales, and market observations.

Does not own
-------------
- Raw extraction parsing (owned by application.investments.input_adapter).
- Lot state mutation (owned by domain.investments.lots.fifo).
"""

from dataclasses import dataclass
from datetime import date

import polars as pl

from personal_finance_etl.application.investments.input_adapter import TaxDataLoader
from personal_finance_etl.application.observability import ObservabilityEmitter, get_global_emitter
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    PresentationKind,
)
from personal_finance_etl.domain.investments.contracts import IsinMasterRecord
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


@dataclass(frozen=True)
class QuantFilePaths:
    """File path mappings for loading investment quant inputs from disk."""

    p_path: str
    s_path: str
    m_path: str
    i_path: str
    b_path: str
    t_path: str
    fx_path: str | None = None


@dataclass(frozen=True)
class QuantDataFrames:
    """Bundle of in-memory Polars DataFrames required for investment quant engine."""

    df_p: pl.DataFrame
    df_s: pl.DataFrame
    df_m: pl.DataFrame
    df_i: pl.DataFrame
    df_b: pl.DataFrame | None = None
    df_t: pl.DataFrame | None = None
    df_fx: pl.DataFrame | None = None


@dataclass(frozen=True)
class QuantRunOptions:
    """Execution options, date boundaries, and status reporting configuration."""

    rules: FinancialRules | None = None
    start_date: date | None = None
    end_date: date | None = None
    run_id: str = "UNKNOWN"


@dataclass
class RunContext:
    """Holds shared state (loaded data, FY table, config) for the execution run."""

    df_p: pl.DataFrame
    df_s: pl.DataFrame
    df_m: pl.DataFrame
    isin_master: dict[str, IsinMasterRecord]
    df_b: pl.DataFrame | None
    fy_table: FYMacroParametersTable
    start_date: date | None
    end_date: date | None
    rules: FinancialRules
    df_fx: pl.DataFrame | None = None
    run_id: str = "UNKNOWN"

    def __post_init__(self) -> None:
        """Initialize transient and computed attributes after dataclass creation."""
        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        self.fx_provider = FXRateProvider(self.df_fx, default_curr)

    @classmethod
    def load(
        cls,
        paths: QuantFilePaths,
        rules: FinancialRules,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> "RunContext":
        """Instantiate RunContext from file paths.

        Parameters
        ----------
        paths : QuantFilePaths
            Bundle of file paths.
        rules : FinancialRules
            Active financial rules configuration.
        start_date : date | None, optional
            Run analysis start boundary.
        end_date : date | None, optional
            Run analysis end boundary.

        Returns
        -------
        RunContext
            Initialized analytics run context.
        """
        df_p, df_s, df_m, isin_master, df_b, df_fx = TaxDataLoader.load_all(
            paths.p_path,
            paths.s_path,
            paths.m_path,
            paths.i_path,
            paths.b_path,
            fx_path=paths.fx_path,
        )
        try:
            df_t = pl.read_csv(paths.t_path)
            fy_table = FYMacroParametersTable(df_t, rules=rules)
        except Exception as e:
            raise Exception(f"Failed to load mandatory Macro Parameters CSV: {e}") from e

        return cls(
            df_p=df_p,
            df_s=df_s,
            df_m=df_m,
            isin_master=isin_master,
            df_b=df_b,
            fy_table=fy_table,
            start_date=start_date,
            end_date=end_date,
            rules=rules,
            df_fx=df_fx,
        )

    @classmethod
    def from_dataframes(
        cls,
        data: QuantDataFrames,
        options: QuantRunOptions,
    ) -> "RunContext":
        """Instantiate RunContext directly from in-memory DataFrames.

        Parameters
        ----------
        data : QuantDataFrames
            Bundle of DataFrames.
        options : QuantRunOptions
            Run configuration options.

        Returns
        -------
        RunContext
            Initialized analytics run context.
        """
        loaded_p, loaded_s, loaded_m, is_m, loaded_b, loaded_fx = (
            TaxDataLoader.load_from_dataframes(
                data.df_p, data.df_s, data.df_m, data.df_i, data.df_b, df_fx=data.df_fx
            )
        )
        assert options.rules is not None
        fy_df = data.df_t if data.df_t is not None else pl.DataFrame()
        fy_table = FYMacroParametersTable(fy_df, rules=options.rules)

        return cls(
            df_p=loaded_p,
            df_s=loaded_s,
            df_m=loaded_m,
            isin_master=is_m,
            df_b=loaded_b,
            fy_table=fy_table,
            start_date=options.start_date,
            end_date=options.end_date,
            rules=options.rules,
            df_fx=loaded_fx,
            run_id=options.run_id,
        )


class AnalyticsContextManager:
    """Manages the initialization of the quantitative analytics engine context."""

    def __init__(
        self,
        status_queue: EventQueue | None = None,
        emitter: ObservabilityEmitter | None = None,
    ):
        self.status_queue = status_queue
        self.emitter = emitter or get_global_emitter()

    def _report(
        self,
        msg: str,
        progress: float,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        presentation_kind: PresentationKind = PresentationKind.PROGRESS,
    ) -> None:
        self.emitter.emit_event(
            event_code=EventCode.QUANT_ENGINE_START,
            message=msg,
            progress=progress,
            severity=severity,
            outcome=(
                EventOutcome.FAILED
                if severity == DiagnosticSeverity.ERROR
                else EventOutcome.COMPLETED
            ),
            presentation_kind=presentation_kind,
            stage=EngineStage.ANALYZING,
        )

    def initialize(
        self,
        data: QuantDataFrames,
        options: QuantRunOptions,
    ) -> tuple[RunContext, list[str]]:
        """Validate input dataframes, initialize RunContext, and extract actionable ISINs.

        Parameters
        ----------
        data : QuantDataFrames
            Bundle of DataFrames.
        options : QuantRunOptions
            Execution options and boundaries.

        Returns
        -------
        tuple[RunContext, list[str]]
            Initialized context and list of distinct ISINs to process.

        Raises
        ------
        ValueError
            If rules is None or required structures are missing.
        """
        self._report(
            "Loading DataFrame memory structures...",
            0.01,
            presentation_kind=PresentationKind.STEP,
        )

        if options.rules is None:
            raise ValueError("Financial rules must be provided")

        ctx = RunContext.from_dataframes(data=data, options=options)

        self._report("Data loaded into Context successfully.", 0.05)

        isins_p = (
            [str(x) for x in ctx.df_p["ISIN"].unique().to_list()]
            if "ISIN" in ctx.df_p.columns
            else []
        )
        isins_s = (
            [str(x) for x in ctx.df_s["ISIN"].unique().to_list()]
            if "ISIN" in ctx.df_s.columns
            else []
        )
        isins_m = (
            [str(x) for x in ctx.df_m["ISIN"].unique().to_list()]
            if "ISIN" in ctx.df_m.columns
            else []
        )
        isins = sorted(set(isins_p + isins_s + isins_m))

        return ctx, isins


__all__ = [
    "AnalyticsContextManager",
    "QuantDataFrames",
    "QuantFilePaths",
    "QuantRunOptions",
    "RunContext",
]
