"""Unit tests for ProviderSymbolMapping, ProviderSymbolRegistry, and symbol builder.

Owns
----
- Verification of ProviderSymbolMapping contract immutability and attributes.
- Verification of ProviderSymbolRegistry O(1) resolution and Mapping protocol compliance.
- Verification of build_provider_symbol_registry extraction and aggregation across market frames.

Does not own
-------------
- Real network HTTP/API calls (owned by integration tests).
- Lakehouse persistence or DuckDB schemas (owned by tests/contracts/test_semantic_inventory.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError

import polars as pl
import pytest

from personal_finance_etl.contracts.market import (
    ProviderSymbolMapping,
    ProviderSymbolRegistry,
)
from personal_finance_etl.infrastructure.providers.market.symbol_mapping import (
    build_provider_symbol_registry,
)


def test_provider_symbol_mapping_immutability() -> None:
    """Verify ProviderSymbolMapping is a frozen slotted dataclass with defaults."""
    mapping = ProviderSymbolMapping(
        canonical_id="US0378331005",
        provider_symbol="AAPL",
    )
    assert mapping.canonical_id == "US0378331005"
    assert mapping.provider_symbol == "AAPL"
    assert mapping.provider_id == "YahooFinance"
    assert mapping.target_currency_code is None

    with pytest.raises(FrozenInstanceError):
        mapping.provider_symbol = "MSFT"  # type: ignore[misc]


def test_provider_symbol_registry_resolution() -> None:
    """Verify ProviderSymbolRegistry resolves symbols and FX pairs accurately."""
    mappings = [
        ProviderSymbolMapping(canonical_id="US0378331005", provider_symbol="AAPL"),
        ProviderSymbolMapping(canonical_id="BM_NIFTY50", provider_symbol="^NSEI"),
        ProviderSymbolMapping(
            canonical_id="USD",
            provider_symbol="USDINR=X",
            target_currency_code="INR",
        ),
        ProviderSymbolMapping(
            canonical_id="USD",
            provider_symbol="USDEUR=X",
            target_currency_code="EUR",
        ),
        ProviderSymbolMapping(
            canonical_id="EUR",
            provider_symbol="EUR=X",
        ),
    ]
    registry = ProviderSymbolRegistry.from_mappings(mappings)

    # Direct security and benchmark symbol resolution
    assert registry.get_symbol("US0378331005") == "AAPL"
    assert registry.get_symbol("BM_NIFTY50") == "^NSEI"
    assert registry.get_symbol("UNKNOWN") is None

    # FX pair direct resolution
    assert registry.get_fx_symbol("USD", "INR") == "USDINR=X"
    assert registry.get_fx_symbol("USD", "EUR") == "USDEUR=X"

    # FX pair fallback to base currency mapping
    assert registry.get_fx_symbol("EUR", "INR") == "EUR=X"

    # Non-existent FX pair
    assert registry.get_fx_symbol("GBP", "JPY") is None


def test_provider_symbol_registry_mapping_protocol() -> None:
    """Verify ProviderSymbolRegistry satisfies collections.abc.Mapping interface."""
    mappings = [
        ProviderSymbolMapping(canonical_id="US001", provider_symbol="AAPL"),
        ProviderSymbolMapping(canonical_id="US002", provider_symbol="GOOGL"),
    ]
    registry = ProviderSymbolRegistry.from_mappings(mappings)

    assert isinstance(registry, Mapping)
    assert len(registry) == 2
    assert "US001" in registry
    assert "US003" not in registry
    assert registry["US001"] == "AAPL"
    assert registry.get("US002") == "GOOGL"
    assert registry.get("UNKNOWN", "DEFAULT") == "DEFAULT"

    with pytest.raises(KeyError):
        _ = registry["MISSING"]

    assert set(iter(registry)) == {"US001", "US002"}
    assert registry.get_symbol_map() == {"US001": "AAPL", "US002": "GOOGL"}


def test_build_provider_symbol_registry_from_frames() -> None:
    """Verify build_provider_symbol_registry parses currency, benchmark, and stock frames."""
    df_currency = pl.DataFrame(
        {
            "UID": ["INR_USD", "INR_EUR", "INR_INACTIVE"],
            "Currency_Code": ["INR", "INR", "INR"],
            "Target_Currency_Code": ["USD", "EUR", "GBP"],
            "yF_Ticker": ["INR=X", "INREUR=X", "INRGBP=X"],
            "Is_Active": [True, True, False],
        }
    ).lazy()

    df_bm_master = pl.DataFrame(
        {
            "ID": ["BM_NIFTY_50", "BM_SENSEX"],
            "Benchmark_Name": ["Nifty 50", "BSE Sensex"],
            "yF_Ticker": ["^NSEI", "^BSESN"],
            "CURRENCY_ID": ["INR_INR", "INR_INR"],
        }
    ).lazy()

    df_bm_mapping = pl.DataFrame(
        {
            "ISIN": ["US0378331005", "US5949181045"],
            "Yahoo_Ticker": ["AAPL", "MSFT"],
        }
    ).lazy()

    registry = build_provider_symbol_registry(
        currency_mapping=df_currency,
        benchmark_master=df_bm_master,
        benchmark_mapping=df_bm_mapping,
    )

    # Currency mappings (active only)
    assert registry.get_symbol("INR_USD") == "INR=X"
    assert registry.get_fx_symbol("INR_USD", "USD") == "INR=X"
    assert registry.get_symbol("INR_EUR") == "INREUR=X"
    assert registry.get_symbol("INR_INACTIVE") is None

    # Benchmark master mappings
    assert registry.get_symbol("BM_NIFTY_50") == "^NSEI"
    assert registry.get_symbol("BM_SENSEX") == "^BSESN"

    # Security/US stock mappings
    assert registry.get_symbol("US0378331005") == "AAPL"
    assert registry.get_symbol("US5949181045") == "MSFT"


def test_build_provider_symbol_registry_handles_empty_or_none() -> None:
    """Verify build_provider_symbol_registry safely handles None or empty inputs."""
    registry = build_provider_symbol_registry()
    assert len(registry) == 0
    assert registry.get_symbol("ANY") is None

    empty_df = pl.DataFrame().lazy()
    registry_empty = build_provider_symbol_registry(
        currency_mapping=empty_df,
        benchmark_master=empty_df,
        benchmark_mapping=empty_df,
    )
    assert len(registry_empty) == 0
