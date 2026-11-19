"""Architectural topology guard tests enforcing source-agnostic topology invariants.

Owns
----
- Invariant 1: Legacy locator, coordinator, and policy_resolver modules permanently demolished.
- Invariant 2: DataExtractor demolished from application.ingestion.
- Invariant 3: Zero occurrences of _inject_configuration_assets in src/.
- Invariant 4: Zero occurrences of categorize_statement_files in src/.
- Invariant 5: Zero occurrences of resolve_legacy_change_detection_policy in src/.
- Invariant 6: BronzeDataContract does not define extraction_attribute as a dataclass field.
- Invariant 7: Settings validation only requires TARGET_DB_BASE_PATH, not legacy paths.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from personal_finance_etl.application import ingestion
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.infrastructure.warehouse.contracts import BronzeDataContract

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "personal_finance_etl"


def test_legacy_modules_demolished() -> None:
    """Verify that legacy locator, coordinator, and policy_resolver files do not exist."""
    locator_path = SRC_ROOT / "infrastructure" / "providers" / "files" / "locator.py"
    coordinator_path = SRC_ROOT / "application" / "ingestion" / "coordinator.py"
    policy_resolver_path = SRC_ROOT / "application" / "ingestion" / "policy_resolver.py"

    assert not locator_path.exists(), f"Legacy {locator_path} must be deleted."
    assert not coordinator_path.exists(), f"Legacy {coordinator_path} must be deleted."
    assert not policy_resolver_path.exists(), f"Legacy {policy_resolver_path} must be deleted."


def test_data_extractor_demolished() -> None:
    """Verify that DataExtractor is not exported or defined in ingestion."""
    assert not hasattr(ingestion, "DataExtractor")


def test_zero_legacy_function_references_in_src() -> None:
    """Verify zero code references to demolished functions in src/."""
    prohibited_names = [
        "_inject_configuration_assets",
        "categorize_statement_files",
        "resolve_legacy_change_detection_policy",
    ]

    for py_file in SRC_ROOT.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for name in prohibited_names:
            assert name not in content, f"Prohibited legacy symbol '{name}' found in {py_file}."


def test_bronze_contract_has_no_extraction_attribute() -> None:
    """Verify extraction_attribute is completely demolished from BronzeDataContract."""
    field_names = {f.name for f in dataclasses.fields(BronzeDataContract)}
    assert "extraction_attribute" not in field_names, (
        "extraction_attribute must not be a dataclass field on BronzeDataContract."
    )
    assert not hasattr(BronzeDataContract, "extraction_attribute"), (
        "extraction_attribute property must be completely demolished from BronzeDataContract."
    )


def test_settings_validation_topology_agnostic() -> None:
    """Verify Settings.validate_config only mandates TARGET_DB_BASE_PATH."""
    settings = Settings(TARGET_DB_BASE_PATH="outputs/Warehouse.duckdb")
    # Must validate cleanly without requiring statements folder or source DB
    settings.validate_config()
    assert settings.TARGET_DB_BASE_PATH == "outputs/Warehouse.duckdb"


def test_settings_ignores_extra_keys() -> None:
    """Verify Settings model_config allows extra configuration fields without error."""
    raw_data = {
        "TARGET_DB_BASE_PATH": "outputs/Warehouse.duckdb",
        "OBSOLETE_CUSTOM_PATH": "some/path",
        "EXTRA_ARBITRARY_FIELD": 42,
    }
    settings = Settings.model_validate(raw_data)
    assert settings.TARGET_DB_BASE_PATH == "outputs/Warehouse.duckdb"
