# pylint: disable=too-many-lines
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

from personal_finance_etl.config.sources.identity import (
    BronzeIdentityStrategy,
    CompositeIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.config.sources.mapping import (
    ColumnMapping,
    dict_to_mapping_list,
)
from personal_finance_etl.config.sources.model import (
    SourceConfig,
    SourceDatasetConfig,
    SourceFieldDeclaration,
)
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    ConstantRule,
    DefaultRule,
    NormalizationRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    DatasetSelector,
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


def _serialize_dataset_selector(sel: DatasetSelector) -> list[str]:
    """Serialize a dataset selector to TOML lines."""
    lines: list[str] = [
        "[datasets.selector]",
        f'provider_type = "{sel.provider_type.value}"',
    ]
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
    return lines


def _serialize_dataset_identity(ident: BronzeIdentityStrategy) -> list[str]:
    """Serialize a Bronze identity strategy to TOML lines."""
    lines: list[str] = [
        "[datasets.identity]",
        f'strategy_type = "{ident.strategy_type}"',
    ]
    if isinstance(ident, SourceFieldIdentity):
        lines.append(f'field = "{ident.field}"')
    elif isinstance(ident, CompositeIdentity):
        fields_str = ", ".join(f'"{f}"' for f in ident.fields)
        lines.append(f"fields = [{fields_str}]")
    else:
        fields_str = ", ".join(f'"{f}"' for f in ident.fields)
        lines.append(f"fields = [{fields_str}]")
        if ident.namespace is not None:
            lines.append(f'namespace = "{ident.namespace}"')
        if ident.version != "v2":
            lines.append(f'version = "{ident.version}"')
    return lines


def _serialize_normalization_rule(norm: NormalizationRule) -> list[str]:
    """Serialize a normalization rule to TOML lines."""
    lines: list[str] = [
        "[[datasets.normalization]]",
        f'rule = "{norm.rule}"',
        f'field = "{norm.field}"',
    ]
    if isinstance(norm, CastRule):
        lines.append(f'target_type = "{norm.target_type}"')
    elif isinstance(norm, ParseDateRule):
        if norm.format is not None:
            lines.append(f'format = "{norm.format}"')
        lines.append(f"strict = {'true' if norm.strict else 'false'}")
    elif isinstance(norm, TrimRule):
        lines.append(f'mode = "{norm.mode}"')
    elif isinstance(norm, NormalizeCaseRule):
        lines.append(f'case = "{norm.case}"')
    elif isinstance(norm, (ConstantRule, DefaultRule)):
        val_str = (
            f'"{norm.value}"'
            if isinstance(norm.value, str)
            else str(norm.value).lower()
            if isinstance(norm.value, bool)
            else str(norm.value)
        )
        lines.append(f"value = {val_str}")
    elif isinstance(norm, NormalizeNullRule):
        nulls = ", ".join(f'"{x}"' for x in norm.null_values)
        lines.append(f"null_values = [{nulls}]")
    else:
        map_entries = ", ".join(f'"{k}" = "{v}"' for k, v in norm.mapping.items())
        lines.append(f"mapping = {{ {map_entries} }}")
        if norm.default is not None:
            lines.append(f'default = "{norm.default}"')
    return lines


def _serialize_dataset_field(field: SourceFieldDeclaration) -> list[str]:
    """Serialize a source field declaration to TOML lines."""
    lines: list[str] = [
        "[[datasets.fields]]",
        f'name = "{field.name}"',
        f'data_type = "{field.data_type}"',
        f"nullable = {'true' if field.nullable else 'false'}",
        f"unique = {'true' if field.unique else 'false'}",
    ]
    if field.description is not None:
        lines.append(f'description = "{field.description}"')
    return lines


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
            lines.extend(_serialize_dataset_selector(ds.selector))

            if ds.identity is not None:
                lines.extend(_serialize_dataset_identity(ds.identity))

            if ds.mapping:
                lines.append("[datasets.mapping]")
                for m in ds.mapping:
                    lines.append(f'"{m.source_field}" = "{m.canonical_field}"')

            for norm in ds.normalization:
                lines.extend(_serialize_normalization_rule(norm))

            for f in ds.fields:
                lines.extend(_serialize_dataset_field(f))

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
            enabled=False,
            description="Retired column mapping dictionary (retired in Phase 030)",
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


_HOUSEHOLD_ZCATEGORY_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "ID": "S_NO",
        "C_IS_DEL": "IS_DEL",
        "C_UTIME": "MODIFY_DATE",
        "uid": "UID",
        "NAME": "CATEGORY_NAME",
        "ORDERSEQ": "ORDER_SEQUENCE",
        "TYPE": "TYPE",
        "STATUS": "STATUS",
        "pUid": "CATEGORY_ID",
        "isSynced": "IS_SYNCED",
        "syncTime": "SYNC_TIME",
        "syncVersion": "SYNC_VERSION",
    }
)

_HOUSEHOLD_ZCATEGORY_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="ID",
        data_type="Int64",
        nullable=False,
        unique=True,
        description="Primary surrogate integer key in source SQLite table",
    ),
    SourceFieldDeclaration(
        name="C_IS_DEL",
        data_type="Int64",
        nullable=True,
        description="Deletion indicator flag",
    ),
    SourceFieldDeclaration(
        name="C_UTIME",
        data_type="Int64",
        nullable=True,
        description="Record modification epoch millisecond timestamp",
    ),
    SourceFieldDeclaration(
        name="uid",
        data_type="String",
        nullable=False,
        unique=True,
        description="Natural unique identifier string for the category",
    ),
    SourceFieldDeclaration(
        name="NAME",
        data_type="String",
        nullable=False,
        description="Category name",
    ),
    SourceFieldDeclaration(
        name="ORDERSEQ",
        data_type="Int64",
        nullable=True,
        description="Category display order sequence",
    ),
    SourceFieldDeclaration(
        name="TYPE",
        data_type="Int64",
        nullable=False,
        description="Category financial classification type code",
    ),
    SourceFieldDeclaration(
        name="STATUS",
        data_type="Int64",
        nullable=True,
        description="Category active or archived status code",
    ),
    SourceFieldDeclaration(
        name="pUid",
        data_type="String",
        nullable=True,
        description="Parent category UID reference for subcategories",
    ),
    SourceFieldDeclaration(
        name="isSynced",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization status flag",
    ),
    SourceFieldDeclaration(
        name="syncTime",
        data_type="Float64",
        nullable=True,
        description="Cloud synchronization epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="syncVersion",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization schema or entity version",
    ),
]

_HOUSEHOLD_ASSET_GROUP_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "DEVICE_ID": "DEVICE_ID",
        "uid": "UID",
        "IS_DEL": "IS_DEL",
        "USETIME": "USE_TIME",
        "ACC_GROUP_NAME": "ASSET_GROUP",
        "TYPE": "TYPE",
        "ORDERSEQ": "ORDER_SEQUENCE",
        "isSynced": "IS_SYNCED",
        "syncTime": "SYNC_TIME",
        "syncVersion": "SYNC_VERSION",
    }
)

_HOUSEHOLD_ASSET_GROUP_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="DEVICE_ID",
        data_type="Int64",
        nullable=True,
        description="Source device identifier integer",
    ),
    SourceFieldDeclaration(
        name="uid",
        data_type="String",
        nullable=False,
        unique=True,
        description="Natural unique identifier string for asset group",
    ),
    SourceFieldDeclaration(
        name="IS_DEL",
        data_type="Int64",
        nullable=True,
        description="Logical deletion flag (0 active, 1 deleted)",
    ),
    SourceFieldDeclaration(
        name="USETIME",
        data_type="Int64",
        nullable=True,
        description="Asset group last use epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="ACC_GROUP_NAME",
        data_type="String",
        nullable=False,
        description="Asset group name",
    ),
    SourceFieldDeclaration(
        name="TYPE",
        data_type="Int64",
        nullable=False,
        description="Asset group financial classification type code",
    ),
    SourceFieldDeclaration(
        name="ORDERSEQ",
        data_type="Int64",
        nullable=True,
        description="Asset group display order sequence",
    ),
    SourceFieldDeclaration(
        name="isSynced",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization status flag",
    ),
    SourceFieldDeclaration(
        name="syncTime",
        data_type="Float64",
        nullable=True,
        description="Cloud synchronization epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="syncVersion",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization schema or entity version",
    ),
]

_HOUSEHOLD_ASSETS_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "ID": "S_NO",
        "CARD_DAY_FIN": "CARD_STATEMENT_DATE",
        "CARD_DAY_PAY": "CARD_PAYMENT_DATE",
        "NIC_NAME": "ASSET_NAME",
        "ORDERSEQ": "ORDER_SEQUENCE",
        "ZDATA": "IS_DEL",
        "ZDATA1": "ASSET_DESCRIPTION",
        "ZDATA2": "NOTES",
        "IS_TRANS_EXPENSE": "TRANSFER_EXPENSE",
        "IS_CARD_AUTO_PAY": "CARD_AUTOPAY",
        "APP_PACKAGE": "APP_PACKAGE",
        "APP_NAME": "APP_NAME",
        "SMS_TEL": "SMS_TEL",
        "SMS_STRING": "SMS_STRING",
        "A_UTIME": "ADDED_TIME",
        "CARD_USAGE_HURDLE_TYPE": "CARD_USAGE_HURDLE_TYPE",
        "CARD_USAGE_HURDLE_START_DATE": "CARD_USAGE_HURDLE_START_DATE",
        "CARD_USAGE_HURDLE_AMOUNT": "CARD_USAGE_HURDLE_AMOUNT",
        "uid": "UID",
        "currencyUid": "CURRENCY_ID",
        "cardAssetUid": "AUTOPAY_ASSET_ID",
        "groupUid": "ASSET_GROUP_ID",
        "isSynced": "IS_SYNCED",
        "syncTime": "SYNC_TIME",
        "syncVersion": "SYNC_VERSION",
    }
)

_HOUSEHOLD_ASSETS_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="ID",
        data_type="Int64",
        nullable=True,
        description="Legacy primary key integer identifier",
    ),
    SourceFieldDeclaration(
        name="CARD_DAY_FIN",
        data_type="String",
        nullable=True,
        description="Credit card statement closing day of month string",
    ),
    SourceFieldDeclaration(
        name="CARD_DAY_PAY",
        data_type="String",
        nullable=True,
        description="Credit card payment due day of month string",
    ),
    SourceFieldDeclaration(
        name="NIC_NAME",
        data_type="String",
        nullable=False,
        description="Asset account nickname or display name",
    ),
    SourceFieldDeclaration(
        name="ORDERSEQ",
        data_type="Int64",
        nullable=True,
        description="Asset display order sequence",
    ),
    SourceFieldDeclaration(
        name="ZDATA",
        data_type="String",
        nullable=True,
        description="Logical deletion flag mapped from ZDATA string",
    ),
    SourceFieldDeclaration(
        name="ZDATA1",
        data_type="String",
        nullable=True,
        description="Asset description note mapped from ZDATA1",
    ),
    SourceFieldDeclaration(
        name="ZDATA2",
        data_type="String",
        nullable=True,
        description="Additional asset notes mapped from ZDATA2",
    ),
    SourceFieldDeclaration(
        name="IS_TRANS_EXPENSE",
        data_type="Int64",
        nullable=True,
        description="Flag indicating if transfer is recorded as expense",
    ),
    SourceFieldDeclaration(
        name="IS_CARD_AUTO_PAY",
        data_type="Int64",
        nullable=True,
        description="Credit card autopay configuration flag",
    ),
    SourceFieldDeclaration(
        name="APP_PACKAGE",
        data_type="String",
        nullable=True,
        description="Associated banking mobile application package name",
    ),
    SourceFieldDeclaration(
        name="APP_NAME",
        data_type="String",
        nullable=True,
        description="Associated banking mobile application name",
    ),
    SourceFieldDeclaration(
        name="SMS_TEL",
        data_type="String",
        nullable=True,
        description="Banking SMS sender telephone or shortcode",
    ),
    SourceFieldDeclaration(
        name="SMS_STRING",
        data_type="String",
        nullable=True,
        description="Banking SMS parser pattern string",
    ),
    SourceFieldDeclaration(
        name="A_UTIME",
        data_type="Int64",
        nullable=True,
        description="Asset creation or addition epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="CARD_USAGE_HURDLE_TYPE",
        data_type="Int64",
        nullable=True,
        description="Credit card annual fee waiver milestone type",
    ),
    SourceFieldDeclaration(
        name="CARD_USAGE_HURDLE_START_DATE",
        data_type="Float64",
        nullable=True,
        description="Credit card fee waiver milestone start date",
    ),
    SourceFieldDeclaration(
        name="CARD_USAGE_HURDLE_AMOUNT",
        data_type="Float64",
        nullable=True,
        description="Credit card spend hurdle target amount",
    ),
    SourceFieldDeclaration(
        name="uid",
        data_type="String",
        nullable=False,
        unique=True,
        description="Natural unique identifier string for asset account",
    ),
    SourceFieldDeclaration(
        name="currencyUid",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to currency",
    ),
    SourceFieldDeclaration(
        name="cardAssetUid",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to autopay source asset",
    ),
    SourceFieldDeclaration(
        name="groupUid",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to asset group",
    ),
    SourceFieldDeclaration(
        name="isSynced",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization status flag",
    ),
    SourceFieldDeclaration(
        name="syncTime",
        data_type="Float64",
        nullable=True,
        description="Cloud synchronization epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="syncVersion",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization schema or entity version",
    ),
]

_HOUSEHOLD_CURRENCY_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "ID": "S_NO",
        "uid": "UID",
        "NAME": "CURRENCY_NAME",
        "ISO": "ISO",
        "MAIN_ISO": "MAIN_ISO",
        "IS_DEL": "IS_DEL",
        "ORDER_SEQ": "ORDER_SEQUENCE",
        "RATE": "RATE",
        "SYMBOL": "SYMBOL",
        "INSERT_TYPE": "INSERT_TYPE",
        "SYMBOL_POSITION": "SYMBOL_POSITION",
        "IS_MAIN_CURRENCY": "IS_MAIN_CURRENCY",
        "IS_SHOW": "IS_SHOW",
        "MODIFY_DATE": "MODIFY_DATE",
        "DECIMAL_POINT": "DECIMAL_POINT",
        "isSynced": "IS_SYNCED",
        "syncTime": "SYNC_TIME",
        "syncVersion": "SYNC_VERSION",
    }
)

_HOUSEHOLD_CURRENCY_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="ID",
        data_type="Int64",
        nullable=True,
        description="Legacy primary key integer identifier",
    ),
    SourceFieldDeclaration(
        name="uid",
        data_type="String",
        nullable=False,
        unique=True,
        description="Natural unique identifier string for currency",
    ),
    SourceFieldDeclaration(
        name="NAME",
        data_type="String",
        nullable=False,
        description="Currency name",
    ),
    SourceFieldDeclaration(
        name="ISO",
        data_type="String",
        nullable=True,
        description="Standard 3-letter currency ISO code",
    ),
    SourceFieldDeclaration(
        name="MAIN_ISO",
        data_type="String",
        nullable=True,
        description="Main base currency ISO code",
    ),
    SourceFieldDeclaration(
        name="IS_DEL",
        data_type="Int64",
        nullable=True,
        description="Logical deletion flag (0 active, 1 deleted)",
    ),
    SourceFieldDeclaration(
        name="ORDER_SEQ",
        data_type="Int64",
        nullable=True,
        description="Currency display order sequence",
    ),
    SourceFieldDeclaration(
        name="RATE",
        data_type="Float64",
        nullable=True,
        description="Exchange rate multiplier relative to base currency",
    ),
    SourceFieldDeclaration(
        name="SYMBOL",
        data_type="String",
        nullable=True,
        description="Currency symbol glyph",
    ),
    SourceFieldDeclaration(
        name="INSERT_TYPE",
        data_type="String",
        nullable=True,
        description="Currency entry insertion type code string",
    ),
    SourceFieldDeclaration(
        name="SYMBOL_POSITION",
        data_type="String",
        nullable=True,
        description="Currency symbol formatting display position string",
    ),
    SourceFieldDeclaration(
        name="IS_MAIN_CURRENCY",
        data_type="Int64",
        nullable=True,
        description="Flag indicating if this is primary base reporting currency",
    ),
    SourceFieldDeclaration(
        name="IS_SHOW",
        data_type="Int64",
        nullable=True,
        description="Visibility flag for currency selector",
    ),
    SourceFieldDeclaration(
        name="MODIFY_DATE",
        data_type="Int64",
        nullable=True,
        description="Currency modification epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="DECIMAL_POINT",
        data_type="Int64",
        nullable=True,
        description="Number of decimal fractional digits for currency",
    ),
    SourceFieldDeclaration(
        name="isSynced",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization status flag",
    ),
    SourceFieldDeclaration(
        name="syncTime",
        data_type="Float64",
        nullable=True,
        description="Cloud synchronization epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="syncVersion",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization schema or entity version",
    ),
]

_HOUSEHOLD_INOUTCOME_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "AID": "S_NO",
        "uid": "UID",
        "assetUid": "ASSET_ID",
        "CARDDIVIDMONTH": "CARDDIVIDMONTH",
        "ctgUid": "CATEGORY_ID",
        "toAssetUid": "TO_ASSET_ID",
        "ZCONTENT": "DESCRIPTION",
        "ZDATE": "TIMESTAMP",
        "WDATE": "DATE",
        "wtime": "TIME",
        "paid": "PAID",
        "DO_TYPE": "TRANSACTION_TYPE",
        "ZMONEY": "BASE_AMOUNT",
        "txUidTrans": "TRANSFER_UID",
        "ZDATA": "FEES_NOTES",
        "SMS_RDATE": "SMS_RDATE",
        "IN_ZMONEY": "LOCAL_AMOUNT",
        "ASSET_NIC": "ASSET_NAME",
        "CATEGORY_NAME": "CATEGORY_NAME",
        "cardDivideUid": "CARD_DIVIDE_ID",
        "CARD_DIVIDE_MONTH_STR": "CARD_DIVIDE_MONTH_STR",
        "MARK": "MARK",
        "txUidFee": "TRANSFER_FEES",
        "SMS_ORIGIN": "SMS_ORIGIN",
        "SMS_PARSE_CONTENT": "SMS_PARSE_CONTENT",
        "IS_DEL": "IS_DEL",
        "UTIME": "UPDATED_TIME",
        "currencyUid": "CURRENCY_ID",
        "AMOUNT_ACCOUNT": "AMOUNT_ACCOUNT",
        "lat": "LAT",
        "lng": "LONG",
        "gstd": "GSTD",
        "isSynced": "IS_SYNCED",
        "syncTime": "SYNC_TIME",
        "syncVersion": "SYNC_VERSION",
    }
)

_HOUSEHOLD_INOUTCOME_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="AID",
        data_type="Int64",
        nullable=True,
        description="Legacy primary key sequence integer",
    ),
    SourceFieldDeclaration(
        name="uid",
        data_type="String",
        nullable=False,
        unique=True,
        description="Natural unique identifier string for transaction",
    ),
    SourceFieldDeclaration(
        name="assetUid",
        data_type="String",
        nullable=False,
        description="Foreign key UID reference to source asset account",
    ),
    SourceFieldDeclaration(
        name="CARDDIVIDMONTH",
        data_type="String",
        nullable=True,
        description="Credit card installment tenure in months",
    ),
    SourceFieldDeclaration(
        name="ctgUid",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to expense/income category",
    ),
    SourceFieldDeclaration(
        name="toAssetUid",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to destination asset account for transfers",
    ),
    SourceFieldDeclaration(
        name="ZCONTENT",
        data_type="String",
        nullable=True,
        description="Transaction description or merchant content",
    ),
    SourceFieldDeclaration(
        name="ZDATE",
        data_type="String",
        nullable=False,
        description="Transaction timestamp in epoch milliseconds or integer date",
    ),
    SourceFieldDeclaration(
        name="WDATE",
        data_type="String",
        nullable=True,
        description="Calendar date string of transaction (YYYY-MM-DD)",
    ),
    SourceFieldDeclaration(
        name="wtime",
        data_type="String",
        nullable=True,
        description="Time string of transaction (HH:MM:SS)",
    ),
    SourceFieldDeclaration(
        name="paid",
        data_type="String",
        nullable=True,
        description="Settlement payment status flag",
    ),
    SourceFieldDeclaration(
        name="DO_TYPE",
        data_type="String",
        nullable=False,
        description="Transaction type code (0 expense, 1 income, 2 transfer)",
    ),
    SourceFieldDeclaration(
        name="ZMONEY",
        data_type="String",
        nullable=False,
        description="Base currency transaction amount",
    ),
    SourceFieldDeclaration(
        name="txUidTrans",
        data_type="String",
        nullable=True,
        description="Foreign key reference UID linking two legs of transfer",
    ),
    SourceFieldDeclaration(
        name="ZDATA",
        data_type="String",
        nullable=True,
        description="Transaction fee, notes, or memo string",
    ),
    SourceFieldDeclaration(
        name="SMS_RDATE",
        data_type="String",
        nullable=True,
        description="Banking SMS receipt date string",
    ),
    SourceFieldDeclaration(
        name="IN_ZMONEY",
        data_type="String",
        nullable=True,
        description="Original currency transaction amount before conversion",
    ),
    SourceFieldDeclaration(
        name="ASSET_NIC",
        data_type="String",
        nullable=True,
        description="Denormalized asset account name at time of transaction",
    ),
    SourceFieldDeclaration(
        name="CATEGORY_NAME",
        data_type="String",
        nullable=True,
        description="Denormalized category name at time of transaction",
    ),
    SourceFieldDeclaration(
        name="cardDivideUid",
        data_type="String",
        nullable=True,
        description="Installment divide UID group identifier",
    ),
    SourceFieldDeclaration(
        name="CARD_DIVIDE_MONTH_STR",
        data_type="String",
        nullable=True,
        description="Installment month fraction string label",
    ),
    SourceFieldDeclaration(
        name="MARK",
        data_type="Int64",
        nullable=True,
        description="User bookmark or star flag",
    ),
    SourceFieldDeclaration(
        name="txUidFee",
        data_type="String",
        nullable=True,
        description="Foreign key reference UID for associated transfer fees",
    ),
    SourceFieldDeclaration(
        name="SMS_ORIGIN",
        data_type="String",
        nullable=True,
        description="Banking SMS sender origin code",
    ),
    SourceFieldDeclaration(
        name="SMS_PARSE_CONTENT",
        data_type="String",
        nullable=True,
        description="Raw matched SMS parse template content",
    ),
    SourceFieldDeclaration(
        name="IS_DEL",
        data_type="Int64",
        nullable=True,
        description="Logical deletion flag (0 active, 1 deleted)",
    ),
    SourceFieldDeclaration(
        name="UTIME",
        data_type="Int64",
        nullable=True,
        description="Transaction update or modification epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="currencyUid",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to transaction currency",
    ),
    SourceFieldDeclaration(
        name="AMOUNT_ACCOUNT",
        data_type="Float64",
        nullable=True,
        description="Asset account balance impact amount",
    ),
    SourceFieldDeclaration(
        name="lat",
        data_type="Float64",
        nullable=True,
        description="Geolocation latitude coordinate",
    ),
    SourceFieldDeclaration(
        name="lng",
        data_type="Float64",
        nullable=True,
        description="Geolocation longitude coordinate",
    ),
    SourceFieldDeclaration(
        name="gstd",
        data_type="String",
        nullable=True,
        description="Goods and Services Tax GST identification or state code",
    ),
    SourceFieldDeclaration(
        name="isSynced",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization status flag",
    ),
    SourceFieldDeclaration(
        name="syncTime",
        data_type="Float64",
        nullable=True,
        description="Cloud synchronization epoch timestamp",
    ),
    SourceFieldDeclaration(
        name="syncVersion",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization schema or entity version",
    ),
]

_HOUSEHOLD_OPENING_BALANCES_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "Z_PK": "Z_PK",
        "Z_ENT": "Z_ENT",
        "Z_OPT": "Z_OPT",
        "ZASSET_GROUP": "ZASSET_GROUP",
        "ZASSET_ID": "ZASSET_ID",
        "ZCATEGORY_ID": "ZCATEGORY_ID",
        "ZOPPOSITEAID": "ZOPPOSITEAID",
        "ZAID": "ZAID",
        "ZCATEGORYID": "ZCATEGORYID",
        "ZCURRENCYID": "ZCURRENCYID",
        "ZFEE_ID": "ZFEE_ID",
        "ZISDEL": "ZISDEL",
        "ZISSYNCED": "ZISSYNCED",
        "ZMARK": "ZMARK",
        "ZSYNCCHECK": "ZSYNCCHECK",
        "ZSYNCVERSION": "ZSYNCVERSION",
        "ZUTIME": "ZUTIME",
        "ZDATE": "ZDATE",
        "ZAMOUNT": "ZAMOUNT",
        "ZAMOUNTACCOUNT": "ZAMOUNTACCOUNT",
        "ZAMOUNTSUB": "ZAMOUNTSUB",
        "ZSYNCTIME": "ZSYNCTIME",
        "ZASSET_NAME": "ZASSET_NAME",
        "ZASSET_NIC": "ZASSET_NIC",
        "ZCARDDIVIDID": "ZCARDDIVIDID",
        "ZCATEGORY_NAME": "ZCATEGORY_NAME",
        "ZCONTENT": "ZCONTENT",
        "ZDO_TYPE": "ZDO_TYPE",
        "ZMONEY": "ZMONEY",
        "ZASSETUID": "ZASSETUID",
        "ZCARDDIVIDEMONTH": "ZCARDDIVIDEMONTH",
        "ZCARDDIVIDEMONTHSTR": "ZCARDDIVIDEMONTHSTR",
        "ZCARDDIVIDEUID": "ZCARDDIVIDEUID",
        "ZCARDTIMESTAMPSTR": "ZCARDTIMESTAMPSTR",
        "ZCATEGORYUID": "ZCATEGORYUID",
        "ZCURRENCY": "ZCURRENCY",
        "ZCURRENCYUID": "ZCURRENCYUID",
        "ZGSTD": "ZGSTD",
        "ZLAT": "ZLAT",
        "ZLNG": "ZLNG",
        "ZMEMO": "ZMEMO",
        "ZPAID": "ZPAID",
        "ZSMSORIGINE": "ZSMSORIGINE",
        "ZSMSPARSECONTENTS": "ZSMSPARSECONTENTS",
        "ZSMSRDATE": "ZSMSRDATE",
        "ZTOASSETUID": "ZTOASSETUID",
        "ZTXDATESTR": "ZTXDATESTR",
        "ZTXUIDFEE": "ZTXUIDFEE",
        "ZTXUIDTRANS": "ZTXUIDTRANS",
        "ZUID": "ZUID",
        "ZWTIME": "ZWTIME",
        "ZZDATA1": "ZZDATA1",
        "ZZDATA2": "ZZDATA2",
    }
)

_HOUSEHOLD_OPENING_BALANCES_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="Z_PK",
        data_type="Int64",
        nullable=False,
        unique=True,
        description="Primary surrogate integer key in opening balances",
    ),
    SourceFieldDeclaration(
        name="Z_ENT",
        data_type="Int64",
        nullable=True,
        description="Entity identifier integer",
    ),
    SourceFieldDeclaration(
        name="Z_OPT",
        data_type="Int64",
        nullable=True,
        description="Optimization sequence integer",
    ),
    SourceFieldDeclaration(
        name="ZASSET_GROUP",
        data_type="Int64",
        nullable=True,
        description="Foreign key reference integer to asset group",
    ),
    SourceFieldDeclaration(
        name="ZASSET_ID",
        data_type="Int64",
        nullable=True,
        description="Foreign key reference integer to asset account",
    ),
    SourceFieldDeclaration(
        name="ZCATEGORY_ID",
        data_type="Int64",
        nullable=True,
        description="Foreign key reference integer to category",
    ),
    SourceFieldDeclaration(
        name="ZOPPOSITEAID",
        data_type="Int64",
        nullable=True,
        description="Opposite transaction identifier integer",
    ),
    SourceFieldDeclaration(
        name="ZAID",
        data_type="Int64",
        nullable=True,
        description="Account asset identifier integer",
    ),
    SourceFieldDeclaration(
        name="ZCATEGORYID",
        data_type="Int64",
        nullable=True,
        description="Category identifier integer",
    ),
    SourceFieldDeclaration(
        name="ZCURRENCYID",
        data_type="Int64",
        nullable=True,
        description="Currency denomination identifier integer",
    ),
    SourceFieldDeclaration(
        name="ZFEE_ID",
        data_type="Int64",
        nullable=True,
        description="Transaction fee identifier integer",
    ),
    SourceFieldDeclaration(
        name="ZISDEL",
        data_type="Int64",
        nullable=True,
        description="Logical deletion flag integer",
    ),
    SourceFieldDeclaration(
        name="ZISSYNCED",
        data_type="Int64",
        nullable=True,
        description="Cloud synchronization status flag integer",
    ),
    SourceFieldDeclaration(
        name="ZMARK",
        data_type="Int64",
        nullable=True,
        description="User bookmark or star flag integer",
    ),
    SourceFieldDeclaration(
        name="ZSYNCCHECK",
        data_type="Int64",
        nullable=True,
        description="Cloud sync checksum verification flag integer",
    ),
    SourceFieldDeclaration(
        name="ZSYNCVERSION",
        data_type="Int64",
        nullable=True,
        description="Cloud sync schema or entity version integer",
    ),
    SourceFieldDeclaration(
        name="ZUTIME",
        data_type="Float64",
        nullable=True,
        description="Record modification epoch timestamp float",
    ),
    SourceFieldDeclaration(
        name="ZDATE",
        data_type="Float64",
        nullable=True,
        description="Opening balance date epoch timestamp float",
    ),
    SourceFieldDeclaration(
        name="ZAMOUNT",
        data_type="Float64",
        nullable=True,
        description="Base currency opening balance amount",
    ),
    SourceFieldDeclaration(
        name="ZAMOUNTACCOUNT",
        data_type="Float64",
        nullable=True,
        description="Asset account currency opening balance amount",
    ),
    SourceFieldDeclaration(
        name="ZAMOUNTSUB",
        data_type="Float64",
        nullable=True,
        description="Sub-account opening balance amount",
    ),
    SourceFieldDeclaration(
        name="ZSYNCTIME",
        data_type="Float64",
        nullable=True,
        description="Cloud sync epoch timestamp float",
    ),
    SourceFieldDeclaration(
        name="ZASSET_NAME",
        data_type="String",
        nullable=True,
        description="Denormalized asset account name string",
    ),
    SourceFieldDeclaration(
        name="ZASSET_NIC",
        data_type="String",
        nullable=True,
        description="Denormalized asset nickname string",
    ),
    SourceFieldDeclaration(
        name="ZCARDDIVIDID",
        data_type="String",
        nullable=True,
        description="Credit card divide installment group identifier",
    ),
    SourceFieldDeclaration(
        name="ZCATEGORY_NAME",
        data_type="String",
        nullable=True,
        description="Denormalized category name string",
    ),
    SourceFieldDeclaration(
        name="ZCONTENT",
        data_type="String",
        nullable=True,
        description="Opening balance description or narrative content",
    ),
    SourceFieldDeclaration(
        name="ZDO_TYPE",
        data_type="String",
        nullable=True,
        description="Transaction type code string",
    ),
    SourceFieldDeclaration(
        name="ZMONEY",
        data_type="String",
        nullable=True,
        description="Opening balance amount string representation",
    ),
    SourceFieldDeclaration(
        name="ZASSETUID",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to asset account",
    ),
    SourceFieldDeclaration(
        name="ZCARDDIVIDEMONTH",
        data_type="String",
        nullable=True,
        description="Credit card divide tenure month string",
    ),
    SourceFieldDeclaration(
        name="ZCARDDIVIDEMONTHSTR",
        data_type="String",
        nullable=True,
        description="Credit card divide month fraction string",
    ),
    SourceFieldDeclaration(
        name="ZCARDDIVIDEUID",
        data_type="String",
        nullable=True,
        description="Credit card divide identifier string",
    ),
    SourceFieldDeclaration(
        name="ZCARDTIMESTAMPSTR",
        data_type="String",
        nullable=True,
        description="Credit card closing timestamp string",
    ),
    SourceFieldDeclaration(
        name="ZCATEGORYUID",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to category",
    ),
    SourceFieldDeclaration(
        name="ZCURRENCY",
        data_type="String",
        nullable=True,
        description="Currency denomination string",
    ),
    SourceFieldDeclaration(
        name="ZCURRENCYUID",
        data_type="String",
        nullable=True,
        description="Foreign key UID reference to currency",
    ),
    SourceFieldDeclaration(
        name="ZGSTD",
        data_type="String",
        nullable=True,
        description="GST tax identification or state code",
    ),
    SourceFieldDeclaration(
        name="ZLAT",
        data_type="Float64",
        nullable=True,
        description="Geolocation latitude coordinate",
    ),
    SourceFieldDeclaration(
        name="ZLNG",
        data_type="Float64",
        nullable=True,
        description="Geolocation longitude coordinate",
    ),
    SourceFieldDeclaration(
        name="ZMEMO",
        data_type="String",
        nullable=True,
        description="Opening balance memo notes string",
    ),
    SourceFieldDeclaration(
        name="ZPAID",
        data_type="String",
        nullable=True,
        description="Settlement payment status string",
    ),
    SourceFieldDeclaration(
        name="ZSMSORIGINE",
        data_type="String",
        nullable=True,
        description="SMS sender origin code string",
    ),
    SourceFieldDeclaration(
        name="ZSMSPARSECONTENTS",
        data_type="String",
        nullable=True,
        description="Raw SMS parsed template content string",
    ),
    SourceFieldDeclaration(
        name="ZSMSRDATE",
        data_type="String",
        nullable=True,
        description="SMS receipt date string",
    ),
    SourceFieldDeclaration(
        name="ZTOASSETUID",
        data_type="String",
        nullable=True,
        description="Destination asset account UID reference string",
    ),
    SourceFieldDeclaration(
        name="ZTXDATESTR",
        data_type="String",
        nullable=True,
        description="Opening balance date string",
    ),
    SourceFieldDeclaration(
        name="ZTXUIDFEE",
        data_type="String",
        nullable=True,
        description="Transfer fee UID reference string",
    ),
    SourceFieldDeclaration(
        name="ZTXUIDTRANS",
        data_type="String",
        nullable=True,
        description="Transfer link UID reference string",
    ),
    SourceFieldDeclaration(
        name="ZUID",
        data_type="String",
        nullable=True,
        description="Record UID string if present",
    ),
    SourceFieldDeclaration(
        name="ZWTIME",
        data_type="String",
        nullable=True,
        description="Opening balance time string",
    ),
    SourceFieldDeclaration(
        name="ZZDATA1",
        data_type="String",
        nullable=True,
        description="Supplemental data field 1 string",
    ),
    SourceFieldDeclaration(
        name="ZZDATA2",
        data_type="String",
        nullable=True,
        description="Supplemental data field 2 string",
    ),
]

_INVESTMENT_MF_ISIN_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="INSTRUMENT_NAME",
        data_type="String",
        nullable=False,
        unique=True,
        description="Mutual fund scheme portfolio name",
    ),
    SourceFieldDeclaration(
        name="ISIN",
        data_type="String",
        nullable=False,
        description="International Securities Identification Number for the mutual fund",
    ),
]

_INVESTMENT_MF_ISIN_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "INSTRUMENT_NAME": "INSTRUMENT_NAME",
        "ISIN": "ISIN",
    }
)

_INVESTMENT_BENCHMARK_MAPPING_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="ISIN",
        data_type="String",
        nullable=False,
        unique=True,
        description="International Securities Identification Number",
    ),
    SourceFieldDeclaration(
        name="Sector",
        data_type="String",
        nullable=True,
        description="Primary industry or economic sector classification",
    ),
    SourceFieldDeclaration(
        name="Industry",
        data_type="String",
        nullable=True,
        description="Granular industry or business activity classification",
    ),
    SourceFieldDeclaration(
        name="Benchmark_ID",
        data_type="String",
        nullable=True,
        description="Foreign key identifier referencing benchmark master catalog",
    ),
    SourceFieldDeclaration(
        name="Yahoo_Ticker",
        data_type="String",
        nullable=True,
        description="Yahoo Finance market ticker symbol",
    ),
    SourceFieldDeclaration(
        name="Tax_Instrument_Type",
        data_type="String",
        nullable=True,
        description="Tax regulatory instrument class (Equity, Debt, Gold, Cash)",
    ),
    SourceFieldDeclaration(
        name="Tax_Instrument_Subtype",
        data_type="String",
        nullable=True,
        description="Tax regulatory instrument subclass (Listed, Unlisted)",
    ),
    SourceFieldDeclaration(
        name="Country",
        data_type="String",
        nullable=True,
        description="Domicile or jurisdiction country name",
    ),
    SourceFieldDeclaration(
        name="Geo",
        data_type="String",
        nullable=True,
        description="Geographic region classification",
    ),
    SourceFieldDeclaration(
        name="Geo_Subtype",
        data_type="String",
        nullable=True,
        description="Granular geographic market designation",
    ),
    SourceFieldDeclaration(
        name="Ticker",
        data_type="String",
        nullable=True,
        description="Exchange trade symbol or local ticker identifier",
    ),
]

_INVESTMENT_BENCHMARK_MAPPING_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "ISIN": "ISIN",
        "Sector": "Sector",
        "Industry": "Industry",
        "Benchmark_ID": "Benchmark_ID",
        "Yahoo_Ticker": "Yahoo_Ticker",
        "Tax_Instrument_Type": "Tax_Instrument_Type",
        "Tax_Instrument_Subtype": "Tax_Instrument_Subtype",
        "Country": "Country",
        "Geo": "Geo",
        "Geo_Subtype": "Geo_Subtype",
        "Ticker": "Ticker",
    }
)

_INVESTMENT_BENCHMARK_MASTER_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="ID",
        data_type="String",
        nullable=False,
        unique=True,
        description="Unique benchmark definition primary key",
    ),
    SourceFieldDeclaration(
        name="Benchmark_Name",
        data_type="String",
        nullable=False,
        description="Human-readable benchmark index title",
    ),
    SourceFieldDeclaration(
        name="yF_Ticker",
        data_type="String",
        nullable=True,
        description="Yahoo Finance ticker symbol for daily historical prices",
    ),
    SourceFieldDeclaration(
        name="Currency",
        data_type="String",
        nullable=True,
        description="Currency code or foreign key reference for benchmark pricing",
    ),
]

_INVESTMENT_BENCHMARK_MASTER_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "ID": "ID",
        "Benchmark_Name": "Benchmark_Name",
        "yF_Ticker": "yF_Ticker",
        "Currency": "Currency",
    }
)

_INVESTMENT_MACRO_PARAMETERS_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="FY",
        data_type="String",
        nullable=False,
        unique=True,
        description="Financial year descriptor string (e.g. 2024-25)",
    ),
    SourceFieldDeclaration(
        name="FY_Start_Date",
        data_type="Date",
        nullable=False,
        description="Financial year start calendar date",
    ),
    SourceFieldDeclaration(
        name="FY_End_Date",
        data_type="Date",
        nullable=False,
        description="Financial year end calendar date",
    ),
    SourceFieldDeclaration(
        name="Debt_MF_Cutoff_Date",
        data_type="Date",
        nullable=True,
        description="Statutory taxation cutoff date for debt mutual funds",
    ),
    SourceFieldDeclaration(
        name="Inflation_Rate",
        data_type="Float64",
        nullable=True,
        description="Annualized macroeconomic inflation rate decimal",
    ),
    SourceFieldDeclaration(
        name="Risk_Free_Rate",
        data_type="Float64",
        nullable=True,
        description="Sovereign risk-free return rate decimal",
    ),
    SourceFieldDeclaration(
        name="Estimated_Ordinary_Income_Tax_Rate",
        data_type="Float64",
        nullable=True,
        description="Estimated marginal ordinary income tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Equity_LTCG_Exemption",
        data_type="Int64",
        nullable=True,
        description="Statutory exempt threshold amount for listed equity LTCG",
    ),
    SourceFieldDeclaration(
        name="Equity_Listed_LTCG",
        data_type="Float64",
        nullable=True,
        description="Listed equity long-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Equity_Listed_STCG",
        data_type="Float64",
        nullable=True,
        description="Listed equity short-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Equity_Unlisted_LTCG",
        data_type="Float64",
        nullable=True,
        description="Unlisted equity long-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Equity_Unlisted_STCG",
        data_type="Float64",
        nullable=True,
        description="Unlisted equity short-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Gold_LTCG",
        data_type="Float64",
        nullable=True,
        description="Sovereign and physical gold long-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Gold_STCG",
        data_type="Float64",
        nullable=True,
        description="Gold short-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Debt_MF_Pre_Cutoff_LTCG",
        data_type="Float64",
        nullable=True,
        description="Pre-cutoff debt mutual fund LTCG tax rate decimal with indexation",
    ),
    SourceFieldDeclaration(
        name="Debt_MF_Pre_Cutoff_STCG",
        data_type="Float64",
        nullable=True,
        description="Pre-cutoff debt mutual fund STCG tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Debt_MF_Post_Cutoff_LTCG",
        data_type="Float64",
        nullable=True,
        description="Post-cutoff debt mutual fund LTCG tax rate decimal without indexation",
    ),
    SourceFieldDeclaration(
        name="Debt_MF_Post_Cutoff_STCG",
        data_type="Float64",
        nullable=True,
        description="Post-cutoff debt mutual fund STCG tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Other_Debt_LTCG",
        data_type="Float64",
        nullable=True,
        description="Other debt securities long-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Other_Debt_STCG",
        data_type="Float64",
        nullable=True,
        description="Other debt securities short-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Default_LTCG",
        data_type="Float64",
        nullable=True,
        description="Fallback default long-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Default_STCG",
        data_type="Float64",
        nullable=True,
        description="Fallback default short-term capital gains tax rate decimal",
    ),
    SourceFieldDeclaration(
        name="Remarks",
        data_type="String",
        nullable=True,
        description="Explanatory or regulatory notes for fiscal parameters",
    ),
]

_INVESTMENT_MACRO_PARAMETERS_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "FY": "FY",
        "FY_Start_Date": "FY_Start_Date",
        "FY_End_Date": "FY_End_Date",
        "Debt_MF_Cutoff_Date": "Debt_MF_Cutoff_Date",
        "Inflation_Rate": "Inflation_Rate",
        "Risk_Free_Rate": "Risk_Free_Rate",
        "Estimated_Ordinary_Income_Tax_Rate": "Estimated_Ordinary_Income_Tax_Rate",
        "Equity_LTCG_Exemption": "Equity_LTCG_Exemption",
        "Equity_Listed_LTCG": "Equity_Listed_LTCG",
        "Equity_Listed_STCG": "Equity_Listed_STCG",
        "Equity_Unlisted_LTCG": "Equity_Unlisted_LTCG",
        "Equity_Unlisted_STCG": "Equity_Unlisted_STCG",
        "Gold_LTCG": "Gold_LTCG",
        "Gold_STCG": "Gold_STCG",
        "Debt_MF_Pre_Cutoff_LTCG": "Debt_MF_Pre_Cutoff_LTCG",
        "Debt_MF_Pre_Cutoff_STCG": "Debt_MF_Pre_Cutoff_STCG",
        "Debt_MF_Post_Cutoff_LTCG": "Debt_MF_Post_Cutoff_LTCG",
        "Debt_MF_Post_Cutoff_STCG": "Debt_MF_Post_Cutoff_STCG",
        "Other_Debt_LTCG": "Other_Debt_LTCG",
        "Other_Debt_STCG": "Other_Debt_STCG",
        "Default_LTCG": "Default_LTCG",
        "Default_STCG": "Default_STCG",
        "Remarks": "Remarks",
    }
)

_MARKET_CURRENCY_MAPPING_FIELDS: list[SourceFieldDeclaration] = [
    SourceFieldDeclaration(
        name="UID",
        data_type="String",
        nullable=False,
        unique=True,
        description="Currency pair composite unique identifier (e.g. INR_USD)",
    ),
    SourceFieldDeclaration(
        name="Currency_Code",
        data_type="String",
        nullable=False,
        description="ISO 4217 base source currency code",
    ),
    SourceFieldDeclaration(
        name="Target_Currency_Code",
        data_type="String",
        nullable=False,
        description="ISO 4217 target reporting currency code",
    ),
    SourceFieldDeclaration(
        name="yF_Ticker",
        data_type="String",
        nullable=True,
        description="Yahoo Finance exchange rate symbol (e.g. USDINR=X)",
    ),
    SourceFieldDeclaration(
        name="Currency_Name",
        data_type="String",
        nullable=True,
        description="Human-readable currency nomenclature",
    ),
    SourceFieldDeclaration(
        name="Is_Active",
        data_type="Boolean",
        nullable=True,
        description="Active rate synchronization indicator flag",
    ),
]

_MARKET_CURRENCY_MAPPING_MAPPING: list[ColumnMapping] = dict_to_mapping_list(
    {
        "UID": "UID",
        "Currency_Code": "Currency_Code",
        "Target_Currency_Code": "Target_Currency_Code",
        "yF_Ticker": "yF_Ticker",
        "Currency_Name": "Currency_Name",
        "Is_Active": "Is_Active",
    }
)


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
            identity=SourceFieldIdentity(field="UID"),
            mapping=list(_HOUSEHOLD_ZCATEGORY_MAPPING),
            fields=list(_HOUSEHOLD_ZCATEGORY_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
            selector=SqliteSelector(table_name="ASSETGROUP"),
            enabled=True,
            description="Household asset grouping table",
            identity=SourceFieldIdentity(field="UID"),
            mapping=list(_HOUSEHOLD_ASSET_GROUP_MAPPING),
            fields=list(_HOUSEHOLD_ASSET_GROUP_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
            enabled=True,
            description="Household financial accounts and assets table",
            identity=SourceFieldIdentity(field="UID"),
            mapping=list(_HOUSEHOLD_ASSETS_MAPPING),
            fields=list(_HOUSEHOLD_ASSETS_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
            selector=SqliteSelector(table_name="CURRENCY"),
            enabled=True,
            description="Household currency denominations table",
            identity=SourceFieldIdentity(field="UID"),
            mapping=list(_HOUSEHOLD_CURRENCY_MAPPING),
            fields=list(_HOUSEHOLD_CURRENCY_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
            selector=SqliteSelector(table_name="INOUTCOME"),
            enabled=True,
            description="Household financial ledger income and expense transactions table",
            identity=SourceFieldIdentity(field="UID"),
            mapping=list(_HOUSEHOLD_INOUTCOME_MAPPING),
            fields=list(_HOUSEHOLD_INOUTCOME_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_isin_csv"),
            dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            selector=CsvSelector(),
            enabled=True,
            identity=SourceFieldIdentity(field="INSTRUMENT_NAME"),
            mapping=list(_INVESTMENT_MF_ISIN_MAPPING),
            fields=list(_INVESTMENT_MF_ISIN_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("benchmark_mapping_csv"),
            dataset_id=DatasetId.INVESTMENT_BENCHMARK_MAPPING,
            selector=CsvSelector(),
            enabled=True,
            identity=SourceFieldIdentity(field="ISIN"),
            mapping=list(_INVESTMENT_BENCHMARK_MAPPING_MAPPING),
            fields=list(_INVESTMENT_BENCHMARK_MAPPING_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("opening_balance_csv"),
            dataset_id=DatasetId.HOUSEHOLD_OPENING_BALANCES,
            selector=CsvSelector(),
            enabled=True,
            identity=SourceFieldIdentity(field="Z_PK"),
            mapping=list(_HOUSEHOLD_OPENING_BALANCES_MAPPING),
            fields=list(_HOUSEHOLD_OPENING_BALANCES_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("benchmark_master_csv"),
            dataset_id=DatasetId.INVESTMENT_BENCHMARK_MASTER,
            selector=CsvSelector(),
            enabled=True,
            identity=SourceFieldIdentity(field="ID"),
            mapping=list(_INVESTMENT_BENCHMARK_MASTER_MAPPING),
            fields=list(_INVESTMENT_BENCHMARK_MASTER_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("macro_parameters_csv"),
            dataset_id=DatasetId.INVESTMENT_MACRO_PARAMETERS,
            selector=CsvSelector(),
            enabled=True,
            identity=SourceFieldIdentity(field="FY"),
            mapping=list(_INVESTMENT_MACRO_PARAMETERS_MAPPING),
            fields=list(_INVESTMENT_MACRO_PARAMETERS_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("currency_mapping_csv"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(),
            enabled=True,
            identity=SourceFieldIdentity(field="UID"),
            mapping=list(_MARKET_CURRENCY_MAPPING_MAPPING),
            fields=list(_MARKET_CURRENCY_MAPPING_FIELDS),
        ),
        SourceDatasetConfig(
            source_id=SourceId("column_master_csv"),
            dataset_id=DatasetId.COMMON_COLUMN_MASTER,
            selector=CsvSelector(),
            enabled=False,
            description="Retired column master mapping dataset (transitional retirement in Phase 030)",
            identity=CompositeIdentity(fields=["TABLE_NAME", "OLD_COLUMN"]),
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
