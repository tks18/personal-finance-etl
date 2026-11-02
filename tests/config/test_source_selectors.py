"""Unit tests for typed dataset selectors and source-dataset binding models.

Owns
----
- Validation and invariant tests for CsvSelector, ExcelSelector, and SqliteSelector.
- Validation, defaults, and round-trip serialization tests for SourceDatasetConfig.
- Provider-selector compatibility tests across CSV, Excel, and SQLite.
- Aggregate cross-model validation tests for source-dataset topologies.

Does not own
------------
- Physical file reading or extractor mechanics (tested in tests/infrastructure/providers).
- Downstream transformation or lakehouse pipeline execution (tested in tests/application).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.config.sources.validation import (
    validate_source_dataset_bindings,
    validate_source_selector_compatibility,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import ProviderType, SourceId


def test_sqlite_selector_valid_and_invariants() -> None:
    """Verify SqliteSelector defaults, field validation, and SQL injection prevention."""
    selector = SqliteSelector(table_name="ZCATEGORY")
    assert selector.provider_type == ProviderType.SQLITE
    assert selector.table_name == "ZCATEGORY"

    # Strips whitespace
    selector_ws = SqliteSelector(table_name="  ASSETS  ")
    assert selector_ws.table_name == "ASSETS"

    # Rejects empty / whitespace table name
    with pytest.raises(ValidationError, match="table_name cannot be empty or whitespace"):
        SqliteSelector(table_name="")

    with pytest.raises(ValidationError, match="table_name cannot be empty or whitespace"):
        SqliteSelector(table_name="   ")

    # Rejects non-string table name
    with pytest.raises(ValidationError, match="table_name must be a string"):
        SqliteSelector.model_validate({"table_name": 1234})

    # Rejects arbitrary SQL / invalid identifiers (semicolons, spaces, statements)
    with pytest.raises(ValidationError, match="valid SQL identifier"):
        SqliteSelector(table_name="ASSETS; DROP TABLE ZCATEGORY;")

    with pytest.raises(ValidationError, match="valid SQL identifier"):
        SqliteSelector(table_name="SELECT * FROM ASSETS")

    with pytest.raises(ValidationError, match="valid SQL identifier"):
        SqliteSelector(table_name="table name with spaces")


def test_excel_selector_valid_and_invariants() -> None:
    """Verify ExcelSelector defaults, sheet name validation, and header row bounds."""
    selector = ExcelSelector(sheet_name="Holdings", header_row=5)
    assert selector.provider_type == ProviderType.EXCEL
    assert selector.sheet_name == "Holdings"
    assert selector.header_row == 5

    # Defaults
    selector_default = ExcelSelector()
    assert selector_default.provider_type == ProviderType.EXCEL
    assert selector_default.sheet_name is None
    assert selector_default.header_row is None

    # Strips whitespace from sheet_name
    selector_ws = ExcelSelector(sheet_name="  Sheet1  ")
    assert selector_ws.sheet_name == "Sheet1"

    # Rejects empty or whitespace sheet_name
    with pytest.raises(ValidationError, match="sheet_name cannot be empty or whitespace"):
        ExcelSelector(sheet_name="")

    with pytest.raises(ValidationError, match="sheet_name cannot be empty or whitespace"):
        ExcelSelector(sheet_name="   ")

    # Rejects negative header_row
    with pytest.raises(ValidationError, match="header_row must be non-negative"):
        ExcelSelector(header_row=-1)

    # Rejects non-integer header_row
    with pytest.raises(ValidationError, match="header_row must be an integer"):
        ExcelSelector.model_validate({"header_row": "five"})

    # Rejects boolean passed as header_row
    with pytest.raises(ValidationError, match="header_row must be an integer"):
        ExcelSelector.model_validate({"header_row": True})


def test_csv_selector_valid_and_invariants() -> None:
    """Verify CsvSelector defaults, delimiter, encoding, and file pattern validation."""
    selector = CsvSelector()
    assert selector.provider_type == ProviderType.CSV
    assert selector.file_pattern is None
    assert selector.delimiter == ","
    assert selector.encoding == "utf-8"
    assert selector.has_header is True

    # Custom valid configuration
    custom_selector = CsvSelector(
        file_pattern="*.csv",
        delimiter="\t",
        encoding="ascii",
        has_header=False,
    )
    assert custom_selector.file_pattern == "*.csv"
    assert custom_selector.delimiter == "\t"
    assert custom_selector.encoding == "ascii"
    assert custom_selector.has_header is False

    # Strips whitespace from file_pattern
    selector_ws = CsvSelector(file_pattern="  data_*.csv  ")
    assert selector_ws.file_pattern == "data_*.csv"

    # Rejects empty / whitespace file_pattern
    with pytest.raises(ValidationError, match="file_pattern cannot be empty or whitespace"):
        CsvSelector(file_pattern="")

    with pytest.raises(ValidationError, match="file_pattern cannot be empty or whitespace"):
        CsvSelector(file_pattern="   ")

    # Rejects empty delimiter
    with pytest.raises(ValidationError, match="delimiter cannot be empty"):
        CsvSelector(delimiter="")

    # Rejects empty / whitespace encoding
    with pytest.raises(ValidationError, match="encoding cannot be empty or whitespace"):
        CsvSelector(encoding="")

    # Rejects unknown encoding codec
    with pytest.raises(ValidationError, match="Unknown text encoding codec"):
        CsvSelector(encoding="non_existent_codec_xyz")


def test_source_dataset_config_validation_and_roundtrip() -> None:
    """Verify SourceDatasetConfig creation, default values, and serialization round-trip."""
    binding = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSETS,
        selector=SqliteSelector(table_name="ASSETS"),
    )
    assert binding.source_id == "household_db"
    assert binding.dataset_id == DatasetId.HOUSEHOLD_ASSETS
    assert binding.enabled is True
    assert binding.description is None
    assert isinstance(binding.selector, SqliteSelector)
    assert binding.selector.table_name == "ASSETS"

    # Dict round-trip
    data_dict = binding.model_dump()
    assert data_dict == {
        "source_id": "household_db",
        "dataset_id": "household_assets",
        "selector": {
            "provider_type": "sqlite",
            "table_name": "ASSETS",
        },
        "enabled": True,
        "description": None,
        "change_detection": None,
    }
    reconstructed_dict = SourceDatasetConfig.model_validate(data_dict)
    assert reconstructed_dict == binding
    assert isinstance(reconstructed_dict.selector, SqliteSelector)
    assert reconstructed_dict.selector.table_name == "ASSETS"

    # JSON round-trip
    json_str = binding.model_dump_json()
    reconstructed_json = SourceDatasetConfig.model_validate_json(json_str)
    assert reconstructed_json == binding
    assert isinstance(reconstructed_json.selector, SqliteSelector)
    assert reconstructed_json.selector.table_name == "ASSETS"


def test_source_dataset_config_excel_and_csv_roundtrip() -> None:
    """Verify round-trip serialization for Excel and CSV selectors inside SourceDatasetConfig."""
    excel_binding = SourceDatasetConfig(
        source_id=SourceId("mf_holdings_source"),
        dataset_id=DatasetId.MARKET_MF_HOLDINGS,
        selector=ExcelSelector(sheet_name="Holdings", header_row=0),
    )
    reconstructed_excel = SourceDatasetConfig.model_validate_json(excel_binding.model_dump_json())
    assert isinstance(reconstructed_excel.selector, ExcelSelector)
    assert reconstructed_excel.selector.sheet_name == "Holdings"
    assert reconstructed_excel.selector.header_row == 0

    csv_binding = SourceDatasetConfig(
        source_id=SourceId("currency_mapping_source"),
        dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
        selector=CsvSelector(file_pattern="CURRENCY_MAPPING.csv", delimiter=","),
    )
    reconstructed_csv = SourceDatasetConfig.model_validate_json(csv_binding.model_dump_json())
    assert isinstance(reconstructed_csv.selector, CsvSelector)
    assert reconstructed_csv.selector.file_pattern == "CURRENCY_MAPPING.csv"
    assert reconstructed_csv.selector.delimiter == ","


def test_source_dataset_config_invalid_dataset_id_rejected() -> None:
    """Verify that arbitrary or unsupported dataset_id strings are strictly rejected."""
    with pytest.raises(ValidationError):
        SourceDatasetConfig.model_validate(
            {
                "source_id": "test_src",
                "dataset_id": "invented_arbitrary_dataset",
                "selector": {"provider_type": "csv"},
            }
        )


def test_source_dataset_config_source_id_validation() -> None:
    """Verify that SourceDatasetConfig validates source_id formatting."""
    with pytest.raises(ValidationError, match="SourceId cannot contain path separators"):
        SourceDatasetConfig(
            source_id=SourceId("path/to/source"),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
        )

    with pytest.raises(ValidationError, match="SourceId cannot be empty or whitespace"):
        SourceDatasetConfig(
            source_id=SourceId("   "),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
        )


def test_validate_source_selector_compatibility() -> None:
    """Verify provider compatibility validation between SourceConfig and DatasetSelector."""
    sqlite_source = SourceConfig(
        source_id=SourceId("db_source"),
        provider_type=ProviderType.SQLITE,
        location="data/Personal_Finance.sqlite",
    )
    excel_source = SourceConfig(
        source_id=SourceId("excel_source"),
        provider_type=ProviderType.EXCEL,
        location="statements/MF",
    )
    csv_source = SourceConfig(
        source_id=SourceId("csv_source"),
        provider_type=ProviderType.CSV,
        location="dependencies/mapping.csv",
    )

    sqlite_sel = SqliteSelector(table_name="ASSETS")
    excel_sel = ExcelSelector(sheet_name="Holdings")
    csv_sel = CsvSelector(file_pattern="*.csv")

    # Compatible pairs accepted
    validate_source_selector_compatibility(sqlite_source, sqlite_sel)
    validate_source_selector_compatibility(excel_source, excel_sel)
    validate_source_selector_compatibility(csv_source, csv_sel)

    # Incompatible pairs rejected
    with pytest.raises(
        ValueError,
        match="Selector provider 'excel' is incompatible with source 'db_source' provider 'sqlite'",
    ):
        validate_source_selector_compatibility(sqlite_source, excel_sel)

    with pytest.raises(
        ValueError,
        match="Selector provider 'csv' is incompatible with source 'db_source' provider 'sqlite'",
    ):
        validate_source_selector_compatibility(sqlite_source, csv_sel)

    with pytest.raises(
        ValueError,
        match="Selector provider 'sqlite' is incompatible with source 'excel_source' provider 'excel'",
    ):
        validate_source_selector_compatibility(excel_source, sqlite_sel)

    with pytest.raises(
        ValueError,
        match="Selector provider 'sqlite' is incompatible with source 'csv_source' provider 'csv'",
    ):
        validate_source_selector_compatibility(csv_source, sqlite_sel)


def test_validate_source_dataset_bindings_aggregate() -> None:
    """Verify aggregate topology validation across multiple sources and dataset bindings."""
    sources = [
        SourceConfig(
            source_id=SourceId("household_db"),
            provider_type=ProviderType.SQLITE,
            location="data/Personal_Finance.sqlite",
        ),
        SourceConfig(
            source_id=SourceId("mf_holdings"),
            provider_type=ProviderType.EXCEL,
            location="statements/Mutual Funds - Holdings",
        ),
        SourceConfig(
            source_id=SourceId("currency_mapping"),
            provider_type=ProviderType.CSV,
            location="data/CURRENCY_MAPPING.csv",
        ),
    ]

    bindings = [
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
            selector=SqliteSelector(table_name="INOUTCOME"),
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_holdings"),
            dataset_id=DatasetId.MARKET_MF_HOLDINGS,
            selector=ExcelSelector(sheet_name="Holdings"),
        ),
        SourceDatasetConfig(
            source_id=SourceId("currency_mapping"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(file_pattern="CURRENCY_MAPPING.csv"),
        ),
    ]

    # Valid topology passes
    validate_source_dataset_bindings(sources, bindings)

    # Also accepts Mapping[SourceId, SourceConfig]
    sources_map = {s.source_id: s for s in sources}
    validate_source_dataset_bindings(sources_map, bindings)


def test_validate_source_dataset_bindings_rejections() -> None:
    """Verify aggregate validation error cases: unknown source, duplicate binding, duplicate source."""
    sources = [
        SourceConfig(
            source_id=SourceId("known_source"),
            provider_type=ProviderType.CSV,
            location="data/test.csv",
        )
    ]

    # 1. Unknown SourceId reference
    bad_binding = [
        SourceDatasetConfig(
            source_id=SourceId("unknown_source"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(),
        )
    ]
    with pytest.raises(ValueError, match="references unknown source_id 'unknown_source'"):
        validate_source_dataset_bindings(sources, bad_binding)

    # 2. Duplicate (source_id, dataset_id) binding
    dup_bindings = [
        SourceDatasetConfig(
            source_id=SourceId("known_source"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(),
        ),
        SourceDatasetConfig(
            source_id=SourceId("known_source"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(),
        ),
    ]
    with pytest.raises(ValueError, match="Duplicate source dataset binding"):
        validate_source_dataset_bindings(sources, dup_bindings)

    # 3. Duplicate source definition in sequence
    dup_sources = [
        SourceConfig(
            source_id=SourceId("same_id"),
            provider_type=ProviderType.CSV,
            location="a.csv",
        ),
        SourceConfig(
            source_id=SourceId("same_id"),
            provider_type=ProviderType.CSV,
            location="b.csv",
        ),
    ]
    with pytest.raises(ValueError, match="Duplicate source definition for source_id 'same_id'"):
        validate_source_dataset_bindings(dup_sources, [])
