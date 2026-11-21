# pyright: reportPrivateUsage=false
"""Enterprise test suite verifying deep domain investment accounting assertions on static fixtures.

Owns
----
- Deep domain verification of Silver investment lots (f_Investment_Analytics_Lot):
  - Deterministic FIFO lot matching and order allocation.
  - Remaining lot quantities, unit cost bases, and closing values.
  - Distinguishing PURCHASE lots from RECONCILIATION lots.
  - Byte-stable deterministic LOT ID verification.
  - Tax holding type classification (STCG vs LTCG).
- Deep domain verification of Silver realized events (f_Investment_Realized_Events):
  - Realized capital gains and losses calculation.
  - Disposed cost basis and sale proceeds alignment.
  - Short-term vs long-term gain classification.
  - Byte-stable deterministic REALIZED IDs.
- Deep domain verification of Silver reconciliation events (f_Investment_Reconciliation_Events):
  - Detection of share discrepancies between broker holdings and transaction order history.
  - Verification of broker quantities, reconstructed quantities, and net quantity adjustments.
  - Deterministic RECON_GROUP and RECON_EVENT IDs.
- Deep domain verification of Gold investment summary marts:
  - gold.investment_by_isin position aggregation.
  - gold.investment_by_instrument_type asset allocation breakdown (Equity vs Mutual Fund).
  - gold.investment_by_portfolio consolidated portfolio valuation.

Does not own
-------------
- Capability graph resolution or pipeline composition (owned by test_capability_composition.py).
- AST architectural boundary enforcement (owned by test_boundaries.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl

from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.model import SourceConfig
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


def _setup_composed_static_env(
    tmp_path: Path,
) -> tuple[Settings, SourceConfiguration]:
    """Create an isolated test environment with static household and investment evidence.

    Parameters
    ----------
    tmp_path : Path
        Temporary testing directory.

    Returns
    -------
    tuple[Settings, SourceConfiguration]
        Isolated Settings and SourceConfiguration pointing to temporary directory.
    """
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    evidence_root = Path("tests/fixtures/evidence")
    shutil.copy(evidence_root / "household" / "SOURCE_DB.sqlite", inputs_dir / "SOURCE_DB.sqlite")
    shutil.copy(
        evidence_root / "reference" / "OPENING_BALANCE.csv", inputs_dir / "OPENING_BALANCE.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "MF_ISIN_MAPPING.csv", inputs_dir / "MF_ISIN_MAPPING.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "MACRO_PARAMETERS.csv", inputs_dir / "MACRO_PARAMETERS.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "CURRENCY_MAPPING.csv", inputs_dir / "CURRENCY_MAPPING.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "BENCHMARK_MAPPING.csv",
        inputs_dir / "BENCHMARK_MAPPING.csv",
    )
    shutil.copy(
        evidence_root / "reference" / "BENCHMARK_MASTER.csv",
        inputs_dir / "BENCHMARK_MASTER.csv",
    )
    shutil.copytree(
        evidence_root / "mutual_funds" / "Mutual Funds - Holdings",
        inputs_dir / "Mutual Funds - Holdings",
    )
    shutil.copytree(
        evidence_root / "mutual_funds" / "Mutual Funds - Orders",
        inputs_dir / "Mutual Funds - Orders",
    )
    shutil.copytree(
        evidence_root / "domestic_stocks" / "Stock PL Statements",
        inputs_dir / "Stock PL Statements",
    )
    shutil.copytree(
        evidence_root / "domestic_stocks" / "Stock - Orders",
        inputs_dir / "Stock - Orders",
    )
    shutil.copytree(
        evidence_root / "us_stocks" / "IND Money (US Stocks)" / "Transaction Reports" / "2025-26",
        inputs_dir / "2025-26",
    )

    base_cfg = get_shan_baseline_source_configuration()
    updated_sources: list[SourceConfig] = []
    for s in base_cfg.sources:
        loc = s.location
        if "SOURCE_DB.sqlite" in loc:
            loc = str(inputs_dir / "SOURCE_DB.sqlite").replace("\\", "/")
        elif "OPENING_BALANCE.csv" in loc:
            loc = str(inputs_dir / "OPENING_BALANCE.csv").replace("\\", "/")
        elif "MF_ISIN_MAPPING.csv" in loc:
            loc = str(inputs_dir / "MF_ISIN_MAPPING.csv").replace("\\", "/")
        elif "MACRO_PARAMETERS.csv" in loc:
            loc = str(inputs_dir / "MACRO_PARAMETERS.csv").replace("\\", "/")
        elif "CURRENCY_MAPPING.csv" in loc:
            loc = str(inputs_dir / "CURRENCY_MAPPING.csv").replace("\\", "/")
        elif "BENCHMARK_MAPPING.csv" in loc:
            loc = str(inputs_dir / "BENCHMARK_MAPPING.csv").replace("\\", "/")
        elif "BENCHMARK_MASTER.csv" in loc:
            loc = str(inputs_dir / "BENCHMARK_MASTER.csv").replace("\\", "/")
        elif "Mutual Funds - Holdings" in loc:
            loc = str(inputs_dir / "Mutual Funds - Holdings").replace("\\", "/")
        elif "Mutual Funds - Orders" in loc:
            loc = str(inputs_dir / "Mutual Funds - Orders").replace("\\", "/")
        elif "Stock PL Statements" in loc:
            loc = str(inputs_dir / "Stock PL Statements").replace("\\", "/")
        elif "Stock - Orders" in loc:
            loc = str(inputs_dir / "Stock - Orders").replace("\\", "/")
        elif "IND Money (US Stocks)" in loc:
            loc = str(inputs_dir / "2025-26").replace("\\", "/")
        updated_sources.append(s.model_copy(update={"location": loc}))

    full_cfg = base_cfg.model_copy(update={"sources": tuple(updated_sources)})

    settings = Settings(
        TARGET_DB_BASE_PATH=str(outputs_dir),
        TARGET_DB_NAME="test_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_cp.sqlite",
        DISABLE_FILE_DISCOVERER=False,
    )
    return settings, full_cfg


def _run_composed_pipeline(tmp_path: Path, rules: FinancialRules) -> tuple[Settings, DuckDBManager]:
    """Execute composed pipeline and return connected DuckDBManager.

    Parameters
    ----------
    tmp_path : Path
        Temporary test directory.
    rules : FinancialRules
        Financial rules model.

    Returns
    -------
    tuple[Settings, DuckDBManager]
        Configured settings and opened DuckDB warehouse connection.
    """
    settings, cfg = _setup_composed_static_env(tmp_path)
    plan = CapabilityPlanner().create_plan(
        [
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )
    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=NullEventQueue(),
        rules=rules,
        emitter=ObservabilityEmitter(),
        plan=plan,
        source_config=cfg,
    )
    orchestrator.run()

    db = DuckDBManager(settings.TARGET_DB_BASE_PATH, settings.TARGET_DB_NAME)
    db.open()
    return settings, db


def test_silver_investment_lots_deterministic_fifo(
    tmp_path: Path,
    rules: FinancialRules,
) -> None:
    """Verify deterministic FIFO lot matching, cost basis, quantities, and byte-stable LOT IDs."""
    _settings, db = _run_composed_pipeline(tmp_path, rules)
    try:
        df_lots: pl.DataFrame = db.conn.query(
            "SELECT Lot_ID, Closing_Date, ISIN, Quantity, Buy_Price, Close_Value, Holding_Type, "
            "Lot_Source_Type, Purchase_ID FROM silver.investment_lot_analytics "
            "ORDER BY Lot_ID"
        ).pl()

        # Exactly 6 tax lots in static test portfolio
        assert df_lots.height == 6

        # 1. Reliance Industries (INE002A01018): 10 shares purchased @ 2400.0, current close 29000.0
        rel_lot = df_lots.filter(pl.col("ISIN") == "INE002A01018")
        assert rel_lot.height == 1
        assert rel_lot.select("Lot_ID").item() == "LOT_3a3131c17b6f5c40"
        assert rel_lot.select("Quantity").item() == 10.0
        assert rel_lot.select("Buy_Price").item() == 2400.0
        assert rel_lot.select("Close_Value").item() == 29000.0
        assert rel_lot.select("Lot_Source_Type").item() == "PURCHASE"
        assert rel_lot.select("Holding_Type").item() == "STCG"
        assert str(rel_lot.select("Purchase_ID").item()).startswith("PURCHASE_")

        # 2. Tata Motors (INE009A01021): 1 Purchase lot (15 shares @ 2000.0) + 1 Recon lot (5 shares)
        tata_lots = df_lots.filter(pl.col("ISIN") == "INE009A01021").sort("Lot_Source_Type")
        assert tata_lots.height == 2

        tata_purch = tata_lots.filter(pl.col("Lot_Source_Type") == "PURCHASE")
        assert tata_purch.select("Lot_ID").item() == "LOT_35de17222ebdc100"
        assert (
            tata_purch.select("Quantity").item() == 15.0
        )  # 20 bought - 5 sold via FIFO = 15 remaining
        assert tata_purch.select("Buy_Price").item() == 2000.0
        assert tata_purch.select("Close_Value").item() == 24000.0

        tata_recon = tata_lots.filter(pl.col("Lot_Source_Type") == "RECONCILIATION")
        assert tata_recon.select("Lot_ID").item() == "LOT_76f2ecbbb0a0825f"
        assert tata_recon.select("Quantity").item() == 5.0
        assert tata_recon.select("Close_Value").item() == 8000.0

        # 3. HDFC Top 100 Fund (INF769K01018): 1 Recon lot (200 units, close 95000.0)
        hdfc_lot = df_lots.filter(pl.col("ISIN") == "INF769K01018")
        assert hdfc_lot.height == 1
        assert hdfc_lot.select("Lot_ID").item() == "LOT_ec3de7e055a6e9fe"
        assert hdfc_lot.select("Quantity").item() == 200.0
        assert hdfc_lot.select("Close_Value").item() == 95000.0
        assert hdfc_lot.select("Lot_Source_Type").item() == "RECONCILIATION"

        # 4. Parag Parikh Flexi Cap (INF879O01019): 1 Purchase lot (90 units) + 1 Recon lot (10.5 units)
        pp_lots = df_lots.filter(pl.col("ISIN") == "INF879O01019").sort("Lot_Source_Type")
        assert pp_lots.height == 2

        pp_purch = pp_lots.filter(pl.col("Lot_Source_Type") == "PURCHASE")
        assert pp_purch.select("Lot_ID").item() == "LOT_6719b66ebe5c4e1f"
        assert pp_purch.select("Quantity").item() == 90.0  # 100.5 bought - 10.5 sold = 90.0
        assert abs(pp_purch.select("Buy_Price").item() - 555.555556) < 1e-4

        pp_recon = pp_lots.filter(pl.col("Lot_Source_Type") == "RECONCILIATION")
        assert pp_recon.select("Lot_ID").item() == "LOT_e66e40e6e0df8cc1"
        assert pp_recon.select("Quantity").item() == 10.5
    finally:
        db.close()


def test_silver_realized_events_capital_gains(
    tmp_path: Path,
    rules: FinancialRules,
) -> None:
    """Verify realized gain/loss calculations, holding classification, and deterministic REALIZED IDs."""
    _settings, db = _run_composed_pipeline(tmp_path, rules)
    try:
        df_realized: pl.DataFrame = db.conn.query(
            "SELECT Realized_Event_ID, Sale_ID, Lot_ID, ISIN, Acquisition_Date, Disposal_Date, "
            "Quantity_Disposed, Acquisition_Price, Sale_Price, Realized_Gain_Loss, Holding_Type "
            "FROM silver.investment_realized_events ORDER BY Realized_Event_ID"
        ).pl()

        # Exactly 2 realized disposal events in static statement evidence
        assert df_realized.height == 2

        # 1. Parag Parikh Flexi Cap partial sale (INF879O01019)
        pp_sale = df_realized.filter(pl.col("ISIN") == "INF879O01019")
        assert pp_sale.height == 1
        assert pp_sale.select("Realized_Event_ID").item() == "REALIZED_47e24b147488242c"
        assert pp_sale.select("Sale_ID").item().startswith("SALE_")
        assert pp_sale.select("Lot_ID").item() == "LOT_6719b66ebe5c4e1f"
        assert pp_sale.select("Quantity_Disposed").item() == 10.5
        assert abs(pp_sale.select("Realized_Gain_Loss").item() - 551.145) < 1e-3
        assert pp_sale.select("Holding_Type").item() == "STCG"

        # 2. Tata Motors partial sale (INE009A01021)
        tata_sale = df_realized.filter(pl.col("ISIN") == "INE009A01021")
        assert tata_sale.height == 1
        assert tata_sale.select("Realized_Event_ID").item() == "REALIZED_f6506a3b3e1f2d35"
        assert tata_sale.select("Sale_ID").item().startswith("SALE_")
        assert tata_sale.select("Lot_ID").item() == "LOT_35de17222ebdc100"
        assert tata_sale.select("Quantity_Disposed").item() == 5.0
        assert tata_sale.select("Acquisition_Price").item() == 1500.0
        assert tata_sale.select("Sale_Price").item() == 1600.0
        assert tata_sale.select("Realized_Gain_Loss").item() == 500.0
        assert tata_sale.select("Holding_Type").item() == "STCG"
    finally:
        db.close()


def test_silver_reconciliation_events_discrepancy_detection(
    tmp_path: Path,
    rules: FinancialRules,
) -> None:
    """Verify reconciliation discrepancy detection, quantity adjustments, and RECON_GROUP IDs."""
    _settings, db = _run_composed_pipeline(tmp_path, rules)
    try:
        df_recon: pl.DataFrame = db.conn.query(
            "SELECT Reconciliation_Group_ID, Reconciliation_Event_ID, ISIN, Reconciliation_Date, "
            "Broker_Quantity, Reconstructed_Quantity, Quantity_Adjustment "
            "FROM silver.investment_reconciliation_events ORDER BY Reconciliation_Event_ID"
        ).pl()

        # All IDs must conform to deterministic byte-stable format
        recon_group_ids = df_recon.select("Reconciliation_Group_ID").to_series().to_list()
        for gid in recon_group_ids:
            assert str(gid).startswith("RECON_GROUP_")

        recon_event_ids = df_recon.select("Reconciliation_Event_ID").to_series().to_list()
        for eid in recon_event_ids:
            assert str(eid).startswith("RECON_EVENT_")

        # Check automated discrepancies where Quantity_Adjustment > 0
        discrepancies = df_recon.filter(pl.col("Quantity_Adjustment") > 0)
        assert discrepancies.height == 3

        # Tata Motors discrepancy: Broker 20.0 vs Reconstructed 15.0 -> +5.0 adjustment
        tata_disc = discrepancies.filter(pl.col("ISIN") == "INE009A01021")
        assert tata_disc.height == 1
        assert tata_disc.select("Broker_Quantity").item() == 20.0
        assert tata_disc.select("Reconstructed_Quantity").item() == 15.0
        assert tata_disc.select("Quantity_Adjustment").item() == 5.0

        # HDFC Top 100 discrepancy: Broker 200.0 vs Reconstructed 0.0 -> +200.0 adjustment
        hdfc_disc = discrepancies.filter(pl.col("ISIN") == "INF769K01018")
        assert hdfc_disc.height == 1
        assert hdfc_disc.select("Broker_Quantity").item() == 200.0
        assert hdfc_disc.select("Reconstructed_Quantity").item() == 0.0
        assert hdfc_disc.select("Quantity_Adjustment").item() == 200.0

        # Parag Parikh discrepancy: Broker 100.5 vs Reconstructed 90.0 -> +10.5 adjustment
        pp_disc = discrepancies.filter(pl.col("ISIN") == "INF879O01019")
        assert pp_disc.height == 1
        assert pp_disc.select("Broker_Quantity").item() == 100.5
        assert pp_disc.select("Reconstructed_Quantity").item() == 90.0
        assert pp_disc.select("Quantity_Adjustment").item() == 10.5
    finally:
        db.close()


def test_gold_investment_summary_marts(
    tmp_path: Path,
    rules: FinancialRules,
) -> None:
    """Verify Gold investment analytics marts aggregate position totals and asset allocation."""
    _settings, db = _run_composed_pipeline(tmp_path, rules)
    try:
        # 1. gold.investment_by_isin
        df_isin: pl.DataFrame = db.conn.query(
            "SELECT ISIN, Total_Quantity, Total_Invested_Value, Total_Current_Value, Unrealized_PL "
            "FROM gold.investment_by_isin ORDER BY ISIN"
        ).pl()

        assert df_isin.height == 4
        isin_set = set(df_isin.select("ISIN").to_series().to_list())
        assert isin_set == {
            "INE002A01018",  # Reliance
            "INE009A01021",  # Tata Motors
            "INF769K01018",  # HDFC Top 100
            "INF879O01019",  # Parag Parikh
        }

        # Sum of current values across all ISINs must match total lot Close_Value exactly
        tot_isin_mv = float(df_isin.select(pl.col("Total_Current_Value").sum()).item())
        lot_close_row = db.conn.query(
            "SELECT SUM(Close_Value) FROM silver.investment_lot_analytics"
        ).fetchone()
        assert lot_close_row is not None
        lot_close_val = float(lot_close_row[0])
        assert abs(tot_isin_mv - lot_close_val) < 1e-4

        # 2. gold.investment_by_instrument_type asset allocation breakdown
        df_type: pl.DataFrame = db.conn.query(
            "SELECT INSTRUMENT_TYPE, Total_Current_Value, Weight "
            "FROM gold.investment_by_instrument_type ORDER BY INSTRUMENT_TYPE"
        ).pl()

        assert df_type.height == 1
        types = set(df_type.select("INSTRUMENT_TYPE").to_series().to_list())
        assert types == {"Equity"}

        # Total allocation weights must sum to 1.0
        tot_weight = float(df_type.select(pl.col("Weight").sum()).item())
        assert abs(tot_weight - 1.0) < 1e-4

        # 3. gold.investment_by_subtype asset breakdown
        df_sub: pl.DataFrame = db.conn.query(
            "SELECT INSTRUMENT_SUBTYPE, Total_Current_Value, Weight "
            "FROM gold.investment_by_subtype ORDER BY INSTRUMENT_SUBTYPE"
        ).pl()

        assert df_sub.height == 3
        subtypes = set(df_sub.select("INSTRUMENT_SUBTYPE").to_series().to_list())
        assert subtypes == {"Direct Stocks", "Flexi Cap", "Large Cap"}
        assert abs(float(df_sub.select(pl.col("Weight").sum()).item()) - 1.0) < 1e-4
        assert (
            abs(float(df_sub.select(pl.col("Total_Current_Value").sum()).item()) - tot_isin_mv)
            < 1e-4
        )

        # 4. gold.investment_by_portfolio
        df_port: pl.DataFrame = db.conn.query(
            "SELECT Total_Current_Value, Weight FROM gold.investment_by_portfolio"
        ).pl()
        assert df_port.height >= 1
        port_mv = float(df_port.select("Total_Current_Value").item())
        assert abs(port_mv - tot_isin_mv) < 1e-4
    finally:
        db.close()
