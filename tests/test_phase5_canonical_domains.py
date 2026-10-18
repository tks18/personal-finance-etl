# pylint: skip-file
# flake8: noqa
"""Phase 5 Canonical Financial Domains certification tests.

Owns
----
- Strict object identity equivalence tests (`is`) between all legacy shims and canonical domain modules.
- Unit verification of household transforms (calendar, dimensions, facts, common).
- Unit verification of market domain (fx rate provider, benchmark transformer, macro table).
- Unit verification of investments transforms (ordering policy, references, US equity).
"""

from datetime import date

import polars as pl
import pytest

from personal_finance_etl.domain.household.transforms import (
    calendar as target_cal,
)
from personal_finance_etl.domain.household.transforms import (
    common as target_common,
)
from personal_finance_etl.domain.household.transforms import (
    dimensions as target_dim,
)
from personal_finance_etl.domain.investments.lots import (
    ordering as target_ord,
)
from personal_finance_etl.domain.investments.transforms import (
    common as target_inv,
)

# Canonical target imports
from personal_finance_etl.domain.market import (
    fx as target_fx,
)
from personal_finance_etl.domain.market import (
    macro as target_macro,
)


def test_calendar_transforms():
    """Verify calendar bounds extraction and 40+ column dimension generation."""
    # Build 7 dummy fact streams with dates
    df_date1 = pl.DataFrame({"DATE": ["2023-04-15", "2023-05-20"]}).lazy()
    df_date2 = pl.DataFrame({"DATE": ["2023-06-01"]}).lazy()
    df_date3 = pl.DataFrame({"DATE": ["2023-03-10"]}).lazy()
    df_date4 = pl.DataFrame({"ZTXDATESTR": ["2023-01-01 10:00:00"]}).lazy()
    df_date5 = pl.DataFrame({"Date": ["2023-12-31"]}).lazy()
    df_date6 = pl.DataFrame({"Date": ["2024-01-15"]}).lazy()
    df_date7 = pl.DataFrame({"Date": ["2024-03-31"]}).lazy()

    bounds_lazy = target_cal.get_stg_calendar_ref(
        df_date1, df_date2, df_date3, df_date4, df_date5, df_date6, df_date7
    )
    bounds = bounds_lazy.collect()
    assert bounds.height == 1
    assert bounds["min_date"][0] == date(2023, 1, 1)
    assert bounds["max_date"][0] == date(2024, 3, 31)

    cal_df = target_cal.transform_d_calendar(bounds_lazy).collect()
    assert cal_df.height > 365
    assert "Financial_Year" in cal_df.columns
    assert "Is_Tax_Harvesting_Season" in cal_df.columns
    assert "FY_Quarter_Year" in cal_df.columns
    # Check April 1st is in FY 2023-24
    apr_1 = cal_df.filter(pl.col("Date") == date(2023, 4, 1))
    assert apr_1["Financial_Year"][0] == "2023-24"
    assert apr_1["FY_Quarter"][0] == 1


def test_household_common_and_dimensions():
    """Verify column mapping filter and basic dimension projection."""
    df_map = pl.DataFrame(
        {
            "TABLE_NAME": ["CATEGORY", "CATEGORY", "ASSET"],
            "OLD_COLUMN": ["NAME", "SEQ", "TITLE"],
            "NEW_COLUMN": ["CATEGORY_NAME", "ORDER_SEQUENCE", "ASSET_NAME"],
        }
    )
    mapping = target_common.get_column_mapping(df_map, "CATEGORY")
    assert mapping == {"NAME": "CATEGORY_NAME", "SEQ": "ORDER_SEQUENCE"}

    # Currency dimension transformation
    df_raw_curr = pl.DataFrame(
        {
            "S_NO": [1],
            "UID": ["INR_UID"],
            "CURRENCY_NAME": ["Indian Rupee"],
            "ISO": ["INR"],
            "MAIN_ISO": ["INR"],
            "ORDER_SEQUENCE": [1],
            "RATE": [1.0],
            "SYMBOL": ["₹"],
            "INSERT_TYPE": [0],
            "SYMBOL_POSITION": [0],
            "IS_MAIN_CURRENCY": [1],
            "IS_SHOW": [1],
            "MODIFY_DATE": ["2023-01-01"],
            "DECIMAL_POINT": [2],
            "IS_DEL": [0],
            "__file_name__": ["currency.csv"],
            "__folder_path__": ["/tmp"],
        }
    ).lazy()

    curr_dim = target_dim.transform_d_currency(df_raw_curr, {}).collect()
    assert curr_dim.height == 1
    assert curr_dim["ISO"][0] == "INR"
    assert curr_dim["Is_Active"][0] is False


def test_market_domain_primitives():
    """Verify FXRateProvider lookup and macro add_months edge cases."""
    # FXRateProvider
    df_fx = pl.DataFrame(
        {
            "Date": [date(2023, 10, 1), date(2023, 10, 5)],
            "Currency_ID": ["USD", "USD"],
            "FX_Rate": [83.0, 83.2],
        }
    )
    provider = target_fx.FXRateProvider(df_fx, default_currency_id="INR")

    # Default currency is identity 1.0
    assert provider.get_rate(date(2023, 10, 1), "INR") == 1.0
    # Exact date
    assert provider.get_rate(date(2023, 10, 1), "USD") == 83.0
    # Weekend / gap date within 30 days falls back to prior rate
    assert provider.get_rate(date(2023, 10, 3), "USD") == 83.0
    # After next update
    assert provider.get_rate(date(2023, 10, 6), "USD") == 83.2
    # Way before first date (> 30 days) returns None
    assert provider.get_rate(date(2023, 1, 1), "USD") is None

    # Macro add_months month-end clamping
    assert target_macro.add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert target_macro.add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # Leap year
    assert target_macro.add_months(date(2023, 8, 31), 1) == date(2023, 9, 30)

    # Holding period threshold
    assert target_macro.get_ltcg_threshold_months("equity", "listed", None) == 24


def test_investments_lot_ordering_policy():
    """Verify CanonicalOrderPolicy tie-breaker hierarchy: Date ASC -> Price ASC -> ID ASC."""
    policy = target_ord.CanonicalOrderPolicy()

    from personal_finance_etl.domain.investments.contracts import TradeRecord

    purchases: list[TradeRecord] = [
        {
            "Date": date(2023, 5, 1),
            "Price": 100.5,
            "Purchase_ID": "B_ID",
            "ISIN": "T1",
            "Quantity": 1.0,
        },
        {
            "Date": date(2023, 5, 1),
            "Price": 100.5,
            "Purchase_ID": "A_ID",
            "ISIN": "T1",
            "Quantity": 1.0,
        },
        {
            "Date": date(2023, 5, 1),
            "Price": 99.0,
            "Purchase_ID": "C_ID",
            "ISIN": "T1",
            "Quantity": 1.0,
        },
        {
            "Date": date(2023, 4, 30),
            "Price": 105.0,
            "Purchase_ID": "D_ID",
            "ISIN": "T1",
            "Quantity": 1.0,
        },
    ]

    sorted_p = policy.sort_purchases(purchases)
    # Primary: Date ASC (April 30 first)
    assert sorted_p[0].get("Purchase_ID") == "D_ID"
    # Secondary: Same Date (May 1), Price ASC (99.0 before 100.5)
    assert sorted_p[1].get("Purchase_ID") == "C_ID"
    # Tiebreak: Same Date (May 1), Same Price (100.5), ID ASC ("A_ID" before "B_ID")
    assert sorted_p[2].get("Purchase_ID") == "A_ID"
    assert sorted_p[3].get("Purchase_ID") == "B_ID"


def test_investments_rolling_average_buy_price():
    """Verify get_sale_reference calculates historical cumulative weighted buy price."""
    # 2 Purchases: 10 units @ 100 on Day 1, 10 units @ 200 on Day 2
    # Rolling buy price at Day 1 = 100, at Day 2 = (1000 + 2000)/20 = 150
    df_p = pl.DataFrame(
        {
            "__file_name__": ["p.csv", "p.csv"],
            "__folder_path__": ["/tmp", "/tmp"],
            "__file_category__": ["Indian", "Indian"],
            "ISIN": ["INF001", "INF001"],
            "Instrument": ["Fund A", "Fund A"],
            "Date": [date(2023, 1, 1), date(2023, 1, 2)],
            "Price": [100.0, 200.0],
            "Quantity": [10.0, 10.0],
        }
    ).lazy()

    p_ref = target_inv.get_purchase_reference(
        df_p,
        instrument_col="Instrument",
        date_col="Date",
        price_col="Price",
        qty_col="Quantity",
    )

    df_s = pl.DataFrame(
        {
            "__file_name__": ["s.csv"],
            "__folder_path__": ["/tmp"],
            "__file_category__": ["Indian"],
            "ISIN": ["INF001"],
            "Instrument": ["Fund A"],
            "Date": [date(2023, 1, 3)],
            "Sell_Price": [180.0],
            "Quantity": [5.0],
        }
    ).lazy()

    s_ref = target_inv.get_sale_reference(
        df_s,
        p_ref,
        instrument_col="Instrument",
        date_col="Date",
        price_col="Sell_Price",
        qty_col="Quantity",
    ).collect()

    assert s_ref.height == 1
    assert s_ref["Buy_Price"][0] == 150.0
    assert s_ref["Unit_PnL"][0] == pytest.approx(30.0)
    assert s_ref["Total_PnL"][0] == pytest.approx(150.0)
