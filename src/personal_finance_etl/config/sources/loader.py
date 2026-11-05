"""Production source configuration loader, schema models, and baseline Shan topology.

Owns
----
- CURRENT_SOURCE_CONFIG_SCHEMA_VERSION: Authoritative configuration schema version string.
- SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS: Supported configuration schema versions.
- CapabilitySelection: Declarative capability selection model.
- SourceConfiguration: Versioned root evidence source configuration model.
- get_shan_baseline_sources: Canonical Shan physical evidence sources specification.
- get_shan_baseline_dataset_bindings: Canonical Shan source-dataset bindings specification.
- get_shan_baseline_source_configuration: Assembled canonical Shan SourceConfiguration instance.

Does not own
-------------
- Physical file reading or provider execution (owned by infrastructure.providers).
- Runtime execution planning (owned by application.pipeline).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, model_validator

from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.config.sources.validation import (
    validate_source_dataset_bindings,
)
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import ProviderType, SourceId

__all__ = [
    "CURRENT_SOURCE_CONFIG_SCHEMA_VERSION",
    "SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS",
    "CapabilitySelection",
    "SourceConfiguration",
    "get_shan_baseline_dataset_bindings",
    "get_shan_baseline_source_configuration",
    "get_shan_baseline_sources",
]

CURRENT_SOURCE_CONFIG_SCHEMA_VERSION: str = "1.0.0"
SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0.0", "1.0"})


class CapabilitySelection(BaseModel):
    """User-configured capability selection specification.

    Parameters
    ----------
    enabled : tuple[CapabilityId, ...] | None, default None
        Explicit list of requested financial execution capabilities.
        If None, all registered capabilities are requested by default.
    """

    enabled: tuple[CapabilityId, ...] | None = None

    @property
    def resolved_capabilities(self) -> frozenset[CapabilityId]:
        """Resolve requested capabilities to a set of CapabilityId enums.

        Returns
        -------
        frozenset[CapabilityId]
            Requested capabilities, or all registered capabilities if not explicitly configured.
        """
        if self.enabled is not None:
            return frozenset(self.enabled)
        return frozenset(CapabilityId)


class SourceConfiguration(BaseModel):
    """Root configuration model defining external physical sources, dataset bindings, and capabilities.

    Parameters
    ----------
    schema_version : str, default CURRENT_SOURCE_CONFIG_SCHEMA_VERSION
        Configuration specification schema version.
    sources : tuple[SourceConfig, ...], default ()
        Configured physical evidence sources.
    datasets : tuple[SourceDatasetConfig, ...], default ()
        Configured bindings of physical sources to canonical datasets.
    capabilities : CapabilitySelection, default CapabilitySelection()
        Configured execution capability selection.
    """

    schema_version: str = CURRENT_SOURCE_CONFIG_SCHEMA_VERSION
    sources: tuple[SourceConfig, ...] = ()
    datasets: tuple[SourceDatasetConfig, ...] = ()
    capabilities: CapabilitySelection = Field(default_factory=CapabilitySelection)

    @model_validator(mode="after")
    def validate_aggregate_semantics(self) -> Self:
        """Validate cross-model semantic consistency across sources, datasets, and capabilities.

        Returns
        -------
        Self
            Validated SourceConfiguration instance.

        Raises
        ------
        ValueError
            If schema_version is unsupported, if any SourceId is duplicated, if any
            dataset references an unknown source, if duplicate (source_id, dataset_id)
            bindings exist, or if selector provider types are incompatible with sources.
        """
        if self.schema_version not in SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS:
            versions = sorted(SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS)
            raise ValueError(
                f"Unsupported configuration schema_version '{self.schema_version}'. "
                f"Supported versions: {versions}."
            )

        validate_source_dataset_bindings(self.sources, self.datasets)
        return self

    def get_source(self, source_id: SourceId | str) -> SourceConfig | None:
        """Retrieve a configured physical source by logical SourceId.

        Parameters
        ----------
        source_id : SourceId | str
            Target logical source identifier.

        Returns
        -------
        SourceConfig | None
            Matching SourceConfig instance if configured, else None.
        """
        target = str(source_id)
        for s in self.sources:
            if str(s.source_id) == target:
                return s
        return None

    def get_dataset_binding(self, dataset_id: DatasetId | str) -> SourceDatasetConfig | None:
        """Retrieve the primary dataset binding for a canonical DatasetId.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Target canonical dataset identifier.

        Returns
        -------
        SourceDatasetConfig | None
            Matching SourceDatasetConfig instance if configured, else None.
        """
        target = str(dataset_id)
        for ds in self.datasets:
            if str(ds.dataset_id) == target:
                return ds
        return None

    def get_source_dataset_bindings(
        self, source_id: SourceId | str
    ) -> tuple[SourceDatasetConfig, ...]:
        """Retrieve all dataset bindings associated with a specific physical source.

        Parameters
        ----------
        source_id : SourceId | str
            Logical source identifier.

        Returns
        -------
        tuple[SourceDatasetConfig, ...]
            All dataset bindings associated with the target source.
        """
        target = str(source_id)
        return tuple(ds for ds in self.datasets if str(ds.source_id) == target)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SourceConfiguration:
        """Construct a validated SourceConfiguration from a Python dictionary.

        Parameters
        ----------
        data : dict[str, object]
            Parsed dictionary representing source configuration.

        Returns
        -------
        SourceConfiguration
            Validated SourceConfiguration instance.
        """
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, object]:
        """Serialize configuration into a primitive dictionary.

        Returns
        -------
        dict[str, object]
            Serialized configuration dictionary.
        """
        return self.model_dump(mode="python")

    @classmethod
    def from_toml(cls, filepath: str | Path | os.PathLike[str]) -> SourceConfiguration:
        """Parse and construct a validated SourceConfiguration from a TOML file.

        Parameters
        ----------
        filepath : str | Path | os.PathLike[str]
            Path to the source configuration TOML file.

        Returns
        -------
        SourceConfiguration
            Validated SourceConfiguration instance.

        Raises
        ------
        FileNotFoundError
            If filepath does not exist.
        ValueError
            If TOML content fails structural or semantic validation.
        """
        path = Path(filepath).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Source configuration file not found: '{path}'")

        with open(path, "rb") as f:
            data = tomllib.load(f)

        return cls.from_dict(data)

    def to_toml(self, filepath: str | Path | os.PathLike[str] | None = None) -> str:
        """Serialize configuration into deterministic, human-readable TOML.

        Parameters
        ----------
        filepath : str | Path | os.PathLike[str] | None, optional
            Optional destination path to write the serialized TOML content.

        Returns
        -------
        str
            Deterministic TOML string representation.
        """
        lines: list[str] = [
            f'schema_version = "{self.schema_version}"',
            "",
            "[capabilities]",
        ]
        if self.capabilities.enabled is not None:
            enabled_str = ", ".join(f'"{c.value}"' for c in self.capabilities.enabled)
            lines.append(f"enabled = [{enabled_str}]")
        else:
            lines.append("# All capabilities active by default")
        lines.append("")

        for src in self.sources:
            lines.append("[[sources]]")
            lines.append(f'source_id = "{src.source_id}"')
            lines.append(f'provider_type = "{src.provider_type.value}"')
            lines.append(f'location = "{src.location}"')
            lines.append(f"enabled = {'true' if src.enabled else 'false'}")
            if src.description is not None:
                lines.append(f'description = "{src.description}"')
            lines.append("")

        for ds in self.datasets:
            lines.append("[[datasets]]")
            lines.append(f'source_id = "{ds.source_id}"')
            lines.append(f'dataset_id = "{ds.dataset_id.value}"')
            lines.append(f"enabled = {'true' if ds.enabled else 'false'}")
            if ds.description is not None:
                lines.append(f'description = "{ds.description}"')
            lines.append("[datasets.selector]")
            sel = ds.selector
            lines.append(f'provider_type = "{sel.provider_type.value}"')
            if isinstance(sel, CsvSelector):
                if sel.file_pattern is not None:
                    lines.append(f'file_pattern = "{sel.file_pattern}"')
                lines.append(f'delimiter = "{sel.delimiter}"')
                lines.append(f'encoding = "{sel.encoding}"')
                lines.append(f"has_header = {'true' if sel.has_header else 'false'}")
            elif isinstance(sel, ExcelSelector):
                if sel.sheet_name is not None:
                    lines.append(f'sheet_name = "{sel.sheet_name}"')
                if sel.header_row is not None:
                    lines.append(f"header_row = {sel.header_row}")
            else:
                lines.append(f'table_name = "{sel.table_name}"')
            lines.append("")

        content = "\n".join(lines)
        if filepath is not None:
            out_path = Path(filepath).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")

        return content


def get_shan_baseline_sources() -> list[SourceConfig]:
    """Return declarative SourceConfig representations of all v9.5.3 external evidence sources.

    Returns
    -------
    list[SourceConfig]
        List of configured physical evidence sources using canonical baseline paths.
    """
    return [
        SourceConfig(
            source_id=SourceId("household_db"),
            provider_type=ProviderType.SQLITE,
            location="inputs/SOURCE_DB.sqlite",
            enabled=True,
            description="External household money management SQLite database backup",
        ),
        SourceConfig(
            source_id=SourceId("mf_isin_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/MF_ISIN_MAPPING.csv",
            enabled=True,
            description="Mutual fund name to ISIN mapping table",
        ),
        SourceConfig(
            source_id=SourceId("benchmark_mapping_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/BENCHMARK_MAPPING.csv",
            enabled=True,
            description="Asset to benchmark index mapping table",
        ),
        SourceConfig(
            source_id=SourceId("opening_balance_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/OPENING_BALANCE.csv",
            enabled=True,
            description="Historical household ledger opening balances",
        ),
        SourceConfig(
            source_id=SourceId("benchmark_master_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/BENCHMARK_MASTER.csv",
            enabled=True,
            description="Benchmark index master catalog",
        ),
        SourceConfig(
            source_id=SourceId("macro_parameters_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/MACRO_PARAMETERS.csv",
            enabled=True,
            description="Macroeconomic and tax policy parameters",
        ),
        SourceConfig(
            source_id=SourceId("currency_mapping_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/CURRENCY_MAPPING.csv",
            enabled=True,
            description="Currency ticker mapping and exchange symbols",
        ),
        SourceConfig(
            source_id=SourceId("column_master_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/COLUMN_MASTER.csv",
            enabled=True,
            description="Transitional column mapping dictionary (scheduled for retirement in Phase 030/035)",
        ),
        SourceConfig(
            source_id=SourceId("mf_holdings_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Mutual Funds - Holdings",
            enabled=True,
            description="Monthly mutual fund holdings spreadsheet directory",
        ),
        SourceConfig(
            source_id=SourceId("mf_orders_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Mutual Funds - Orders",
            enabled=True,
            description="Monthly mutual fund orders and transactions spreadsheet directory",
        ),
        SourceConfig(
            source_id=SourceId("stock_pl_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Stock PL Statements",
            enabled=True,
            description="Monthly stock profit and loss statement directory",
        ),
        SourceConfig(
            source_id=SourceId("stock_orders_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Stock - Orders",
            enabled=True,
            description="Monthly stock order execution statement directory",
        ),
        SourceConfig(
            source_id=SourceId("us_stock_transactions"),
            provider_type=ProviderType.CSV,
            location="inputs/Statements/IND Money (US Stocks)/Transaction Reports",
            enabled=False,
            description="Optional US stock transaction reports directory (default disabled)",
        ),
    ]


def get_shan_baseline_dataset_bindings() -> list[SourceDatasetConfig]:
    """Return declarative SourceDatasetConfig bindings covering all external Bronze datasets.

    Returns
    -------
    list[SourceDatasetConfig]
        List of source-to-dataset bindings for all 17 externally supplied Bronze datasets.
    """
    return [
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            selector=SqliteSelector(table_name="ZCATEGORY"),
            enabled=True,
            description="Household expense categories table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
            selector=SqliteSelector(table_name="ASSETGROUP"),
            enabled=True,
            description="Household asset grouping table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
            enabled=True,
            description="Household financial accounts and assets table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
            selector=SqliteSelector(table_name="CURRENCY"),
            enabled=True,
            description="Household currency denominations table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
            selector=SqliteSelector(table_name="INOUTCOME"),
            enabled=True,
            description="Household financial ledger income and expense transactions table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_isin_csv"),
            dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("benchmark_mapping_csv"),
            dataset_id=DatasetId.INVESTMENT_BENCHMARK_MAPPING,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("opening_balance_csv"),
            dataset_id=DatasetId.HOUSEHOLD_OPENING_BALANCES,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("benchmark_master_csv"),
            dataset_id=DatasetId.INVESTMENT_BENCHMARK_MASTER,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("macro_parameters_csv"),
            dataset_id=DatasetId.INVESTMENT_MACRO_PARAMETERS,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("currency_mapping_csv"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("column_master_csv"),
            dataset_id=DatasetId.COMMON_COLUMN_MASTER,
            selector=CsvSelector(),
            enabled=True,
            description="Transitional column master mapping dataset (scheduled for retirement in Phase 030/035)",
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_holdings_excel"),
            dataset_id=DatasetId.MARKET_MF_HOLDINGS,
            selector=ExcelSelector(sheet_name="Holdings"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_orders_excel"),
            dataset_id=DatasetId.INVESTMENT_MF_ORDERS,
            selector=ExcelSelector(sheet_name="Transactions"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("stock_pl_excel"),
            dataset_id=DatasetId.MARKET_STOCK_HOLDINGS,
            selector=ExcelSelector(sheet_name="Trade Level"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("stock_orders_excel"),
            dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
            selector=ExcelSelector(sheet_name="Sheet1", header_row=5),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("us_stock_transactions"),
            dataset_id=DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
            selector=CsvSelector(file_pattern="*.csv"),
            enabled=False,
            description="Optional US stock transactions reports",
        ),
    ]


def get_shan_baseline_source_configuration() -> SourceConfiguration:
    """Return the assembled canonical Shan SourceConfiguration instance with all capabilities active.

    Returns
    -------
    SourceConfiguration
        Validated SourceConfiguration instance representing the canonical Shan evidence topology.
    """
    return SourceConfiguration(
        schema_version=CURRENT_SOURCE_CONFIG_SCHEMA_VERSION,
        sources=tuple(get_shan_baseline_sources()),
        datasets=tuple(get_shan_baseline_dataset_bindings()),
        capabilities=CapabilitySelection(enabled=tuple(CapabilityId)),
    )
