"""Asset-specific ingestion strategy coordination.

Owns
----
- Polymorphic strategy protocols for asset ingestion (AssetPipeline).
- Stock, US Stock, and Mutual Fund trade and market data preparation.
- Mapping extracted raw evidence to intermediate asset-specific references.

Does not own
-------------
- Low-level statement file parsing (owned by infrastructure.providers.files).
- Tax lot clearing or performance calculation (owned by domain.investments).
- Lakehouse schema management (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.extraction import AssetPipelineResult, ExtractionResult
from personal_finance_etl.domain.investments.transforms.common import (
    get_purchase_reference,
    get_sale_reference,
)
from personal_finance_etl.domain.investments.transforms.indian_equity import (
    get_base_stock_transactions,
    get_stg_stock_market_data,
    get_stg_stock_market_data_ref,
    get_stg_stock_master_ref,
    transform_stg_stock_trades,
)
from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    get_base_mf_transactions,
    get_stg_mf_market_data,
    get_stg_mf_market_data_ref,
    get_stg_mf_master_ref,
    transform_stg_mf_trades,
)
from personal_finance_etl.domain.investments.transforms.us_equity import (
    get_base_us_stock_transactions,
    get_stg_us_stock_master_ref,
    transform_stg_us_stock_trades,
)

__all__ = [
    "AssetPipeline",
    "MutualFundPipeline",
    "StockPipeline",
    "USStockPipeline",
]


@runtime_checkable
class AssetPipeline(Protocol):
    """Protocol for asset-specific extraction and trade preparation."""

    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        rules: FinancialRules,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        """Process the asset-specific logic and return AssetPipelineResult."""
        ...


class StockPipeline:
    """Ingestion strategy for Indian domestic equities."""

    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        rules: FinancialRules,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        logger.debug("Parsing unstructured Stock Excel files...")
        market_data = get_stg_stock_market_data(
            extracted.stock_market_data_raw, rules.DEFAULT_CURRENCY_ID
        )
        market_data_ref = get_stg_stock_market_data_ref(market_data)

        logger.debug("Parsing Stock Trade Orders...")
        base_orders = get_base_stock_transactions(extracted.stock_transactions_raw)
        purchase_trans = transform_stg_stock_trades(base_orders, trade_type="BUY")
        sale_trans = transform_stg_stock_trades(base_orders, trade_type="SELL")

        logger.debug("Aggregating Stock Purchases...")
        purchase_ref = get_purchase_reference(
            purchase_trans, "Stock name", "Execution date and time", "Price", "Quantity"
        )

        logger.debug("Processing Stock Sales...")
        sale_ref = get_sale_reference(
            sale_trans, purchase_ref, "Stock name", "Execution date and time", "Price", "Quantity"
        )

        master_ref = get_stg_stock_master_ref(market_data, d_asset_subcategory_lazy)

        return AssetPipelineResult(
            market_data=market_data,
            market_data_ref=market_data_ref,
            purchase_ref=purchase_ref,
            sale_ref=sale_ref,
            master_ref=master_ref,
        )


class USStockPipeline:
    """Ingestion strategy for US equities and global assets."""

    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        rules: FinancialRules,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        logger.debug("Parsing US Stock Trade Orders...")
        base_orders = get_base_us_stock_transactions(extracted.us_stock_transactions_raw)
        purchase_trans = transform_stg_us_stock_trades(base_orders, trade_type="BUY")
        sale_trans = transform_stg_us_stock_trades(base_orders, trade_type="SELL")

        logger.debug("Aggregating US Stock Purchases...")
        purchase_ref = get_purchase_reference(
            purchase_trans,
            "Instrument Name",
            "Date",
            "Price",
            "Quantity",
            extra_group_cols=["Price_Local", "FX_Rate", "CURRENCY_ID"],
        ).with_columns((pl.col("Quantity") * pl.col("Price_Local")).alias("Value_Local"))

        logger.debug("Processing US Stock Sales...")
        sale_ref = (
            get_sale_reference(
                sale_trans,
                purchase_ref,
                "Instrument Name",
                "Date",
                "Price",
                "Quantity",
                extra_group_cols=["Price_Local", "FX_Rate", "CURRENCY_ID"],
            )
            .with_columns((pl.col("Quantity") * pl.col("Price_Local")).alias("Sell_Value_Local"))
            .rename({"Price_Local": "Sell_Price_Local"})
        )

        master_ref = get_stg_us_stock_master_ref(base_orders, d_asset_subcategory_lazy)

        empty_market_data = pl.LazyFrame(
            schema={
                "Date": pl.Date,
                "ISIN": pl.String,
                "__file_category__": pl.String,
                "Quantity": pl.Float64,
                "Closing_Price_Local": pl.Float64,
                "Buy_Price_Local": pl.Float64,
                "Closing_Value_Local": pl.Float64,
                "Buy_Value_Local": pl.Float64,
                "FX_Rate": pl.Float64,
                "Closing_Price": pl.Float64,
                "Buy_Price": pl.Float64,
                "Closing_Value": pl.Float64,
                "Buy_Value": pl.Float64,
                "Unit_PnL": pl.Float64,
                "Total_PnL": pl.Float64,
                "CURRENCY_ID": pl.String,
            }
        )

        return AssetPipelineResult(
            market_data=empty_market_data,
            market_data_ref=empty_market_data,
            purchase_ref=purchase_ref,
            sale_ref=sale_ref,
            master_ref=master_ref,
        )


class MutualFundPipeline:
    """Ingestion strategy for Indian domestic Mutual Funds."""

    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        rules: FinancialRules,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        logger.debug("Parsing unstructured Mutual Fund Excel files...")
        mapping = extracted.stg_mf_isin_mapping
        market_data = get_stg_mf_market_data(
            extracted.mf_market_data_raw, mapping, rules.DEFAULT_CURRENCY_ID
        )
        market_data_ref = get_stg_mf_market_data_ref(market_data)

        logger.debug("Parsing Mutual Fund Trade Orders...")
        base_orders = get_base_mf_transactions(extracted.mf_transactions_raw)
        purchase_trans = transform_stg_mf_trades(
            base_orders, mapping, rules.MF_SCHEME_MAPPINGS, trade_type="PURCHASE"
        )
        sale_trans = transform_stg_mf_trades(
            base_orders, mapping, rules.MF_SCHEME_MAPPINGS, trade_type="REDEEM"
        )

        logger.debug("Aggregating Mutual Fund Purchases...")
        purchase_ref = get_purchase_reference(
            purchase_trans, "Final Scheme Name", "Date", "NAV", "Units"
        )

        logger.debug("Processing Mutual Fund Sales...")
        sale_ref = get_sale_reference(
            sale_trans, purchase_ref, "Final Scheme Name", "Date", "NAV", "Units"
        )

        master_ref = get_stg_mf_master_ref(
            market_data, purchase_trans, sale_trans, d_asset_subcategory_lazy
        )

        return AssetPipelineResult(
            market_data=market_data,
            market_data_ref=market_data_ref,
            purchase_ref=purchase_ref,
            sale_ref=sale_ref,
            master_ref=master_ref,
        )
