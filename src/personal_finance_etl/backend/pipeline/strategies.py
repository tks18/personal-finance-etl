import logging
from typing import Protocol

import polars as pl

from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.transform.investments import (
    get_purchase_reference,
    get_sale_reference,
)
from personal_finance_etl.backend.transform.mutual_funds import (
    get_base_mf_transactions,
    get_stg_mf_market_data,
    get_stg_mf_market_data_ref,
    get_stg_mf_master_ref,
    transform_stg_mf_trades,
)
from personal_finance_etl.backend.transform.stocks import (
    get_base_stock_transactions,
    get_stg_stock_market_data,
    get_stg_stock_market_data_ref,
    get_stg_stock_master_ref,
    transform_stg_stock_trades,
)
from personal_finance_etl.backend.utils.models import AssetPipelineResult, ExtractionResult


class AssetPipeline(Protocol):
    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        cfg: Settings,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        """
        Process the asset-specific logic.
        Must return AssetPipelineResult.
        """
        ...


class StockPipeline:
    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        cfg: Settings,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        logger.info("Parsing unstructured Stock Excel files...")
        market_data = get_stg_stock_market_data(
            extracted.stock_market_data_raw, cfg.DEFAULT_CURRENCY_ID
        )
        market_data_ref = get_stg_stock_market_data_ref(market_data)

        logger.info("Parsing Stock Trade Orders...")
        base_orders = get_base_stock_transactions(extracted.stock_transactions_raw)
        purchase_trans = transform_stg_stock_trades(base_orders, trade_type="BUY")
        sale_trans = transform_stg_stock_trades(base_orders, trade_type="SELL")

        logger.info("Aggregating Stock Purchases...")
        purchase_ref = get_purchase_reference(
            purchase_trans, "Stock name", "Execution date and time", "Price", "Quantity"
        )

        logger.info("Processing Stock Sales...")
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


class MutualFundPipeline:
    def process(
        self,
        extracted: ExtractionResult,
        d_asset_subcategory_lazy: pl.LazyFrame,
        cfg: Settings,
        logger: logging.Logger,
    ) -> AssetPipelineResult:
        logger.info("Parsing unstructured Mutual Fund Excel files...")
        mapping = extracted.stg_mf_isin_mapping
        market_data = get_stg_mf_market_data(
            extracted.mf_market_data_raw, mapping, cfg.DEFAULT_CURRENCY_ID
        )
        market_data_ref = get_stg_mf_market_data_ref(market_data)

        logger.info("Parsing Mutual Fund Trade Orders...")
        base_orders = get_base_mf_transactions(extracted.mf_transactions_raw)
        purchase_trans = transform_stg_mf_trades(
            base_orders, mapping, cfg.MF_SCHEME_MAPPINGS, trade_type="PURCHASE"
        )
        sale_trans = transform_stg_mf_trades(
            base_orders, mapping, cfg.MF_SCHEME_MAPPINGS, trade_type="REDEEM"
        )

        logger.info("Aggregating Mutual Fund Purchases...")
        purchase_ref = get_purchase_reference(
            purchase_trans, "Final Scheme Name", "Date", "NAV", "Units"
        )

        logger.info("Processing Mutual Fund Sales...")
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
