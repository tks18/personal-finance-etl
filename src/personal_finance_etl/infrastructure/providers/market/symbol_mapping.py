"""Provider symbol mapping builders and extraction adapters.

Owns
----
- Construction of immutable ProviderSymbolRegistry instances from configuration and raw mapping tables.
- Extraction of vendor-specific market tickers from currency, benchmark, and security mapping frames.

Does not own
-------------
- ProviderSymbolRegistry or ProviderSymbolMapping contract models (owned by contracts.market).
- Network HTTP / API extraction loops (owned by infrastructure.providers.market adapters).
- Canonical Lakehouse DDL persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.contracts.market import (
    ProviderSymbolMapping,
    ProviderSymbolRegistry,
)

__all__ = ["build_provider_symbol_registry"]


def build_provider_symbol_registry(
    currency_mapping: pl.LazyFrame | pl.DataFrame | None = None,
    benchmark_master: pl.LazyFrame | pl.DataFrame | None = None,
    benchmark_mapping: pl.LazyFrame | pl.DataFrame | None = None,
    default_provider_id: str = "YahooFinance",
) -> ProviderSymbolRegistry:
    """Build an immutable ProviderSymbolRegistry from extracted raw mapping frames.

    Parameters
    ----------
    currency_mapping : pl.LazyFrame | pl.DataFrame | None, default None
        Raw currency mapping records (containing UID, yF_Ticker, and Target_Currency_Code).
    benchmark_master : pl.LazyFrame | pl.DataFrame | None, default None
        Raw benchmark master records (containing ID and yF_Ticker).
    benchmark_mapping : pl.LazyFrame | pl.DataFrame | None, default None
        Raw benchmark instrument mapping records (containing ISIN and Yahoo_Ticker).
    default_provider_id : str, default "YahooFinance"
        Default provider identifier to assign to mappings.

    Returns
    -------
    ProviderSymbolRegistry
        Immutable provider symbol registry containing all mapped symbols.
    """
    mappings: list[ProviderSymbolMapping] = []

    if currency_mapping is not None:
        df_curr = (
            currency_mapping.collect()
            if isinstance(currency_mapping, pl.LazyFrame)
            else currency_mapping
        )
        if not df_curr.is_empty():
            for row in df_curr.to_dicts():
                is_active = row.get("Is_Active")
                if is_active is False:
                    continue
                uid = str(row.get("UID") or row.get("Currency_Code") or "").strip()
                ticker = str(row.get("yF_Ticker", "")).strip()
                target_code = row.get("Target_Currency_Code")
                target_str = str(target_code).strip() if target_code else None

                if uid and ticker:
                    mappings.append(
                        ProviderSymbolMapping(
                            canonical_id=uid,
                            provider_symbol=ticker,
                            provider_id=default_provider_id,
                            target_currency_code=target_str,
                        )
                    )

    if benchmark_master is not None:
        df_bm = (
            benchmark_master.collect()
            if isinstance(benchmark_master, pl.LazyFrame)
            else benchmark_master
        )
        if not df_bm.is_empty():
            for row in df_bm.to_dicts():
                bm_id = str(row.get("ID", "")).strip()
                ticker = str(row.get("yF_Ticker", "")).strip()
                if bm_id and ticker:
                    mappings.append(
                        ProviderSymbolMapping(
                            canonical_id=bm_id,
                            provider_symbol=ticker,
                            provider_id=default_provider_id,
                        )
                    )

    if benchmark_mapping is not None:
        df_map = (
            benchmark_mapping.collect()
            if isinstance(benchmark_mapping, pl.LazyFrame)
            else benchmark_mapping
        )
        if not df_map.is_empty():
            for row in df_map.to_dicts():
                isin = str(row.get("ISIN", "")).strip()
                ticker = str(row.get("Yahoo_Ticker") or row.get("yF_Ticker") or "").strip()
                if isin and ticker:
                    mappings.append(
                        ProviderSymbolMapping(
                            canonical_id=isin,
                            provider_symbol=ticker,
                            provider_id=default_provider_id,
                        )
                    )

    return ProviderSymbolRegistry.from_mappings(mappings)
