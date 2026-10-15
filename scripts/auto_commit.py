"""Automated Git Commit Tool adhering to Commitlint and Conventional Commits.

Owns
----
- Automatic generation of Conventional Commit messages within 72-80 character limit.
- Individual file staging and granular committing for refactoring workflows.
- Dry-run preview of commit headers and scopes.
- Reusable across all refactoring phases (Phase 0 through Phase 8).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Explicit commit overrides for known files during the refactoring phases
KNOWN_COMMIT_MESSAGES: dict[str, str] = {
    # Phase 0 Architecture
    "tests/test_architecture_boundaries.py": "test(architecture): add AST layer boundary enforcement test",
    # Phase 1 Contracts
    "src/personal_finance_etl/contracts/__init__.py": "refactor(contracts): declare lifecycle and extraction exports",
    "src/personal_finance_etl/contracts/lifecycle.py": "refactor(contracts): define CommitState and FailureDomain contracts",
    "src/personal_finance_etl/contracts/logging.py": "refactor(contracts): define LogLevel enum contract",
    "src/personal_finance_etl/contracts/extraction.py": "refactor(contracts): define extraction result and error contracts",
    "src/personal_finance_etl/contracts/recovery.py": "refactor(contracts): define snapshot and restore result contracts",
    "src/personal_finance_etl/contracts/application.py": "refactor(contracts): define engine execution and status contracts",
    "src/personal_finance_etl/domain/common/calculation.py": "refactor(domain/common): define financial calculation results",
    "src/personal_finance_etl/domain/common/validation.py": "refactor(domain/common): define validation exceptions and parsing",
    "src/personal_finance_etl/domain/market/fx.py": "refactor(domain/market): define FXObservation data contract",
    "src/personal_finance_etl/domain/investments/contracts.py": "refactor(domain/investments): define tax lot and realized records",
    "tests/test_phase1_contracts.py": "test(contracts): add Phase 1 contracts and re-export tests",
    # Phase 1 Legacy Deactivations
    "src/personal_finance_etl/backend/types/calculation.py": "refactor(legacy): deactivate types/calculation and delegate",
    "src/personal_finance_etl/backend/types/validation.py": "refactor(legacy): deactivate types/validation and delegate",
    "src/personal_finance_etl/backend/types/fx.py": "refactor(legacy): deactivate types/fx and delegate",
    "src/personal_finance_etl/backend/types/failure.py": "refactor(legacy): deactivate types/failure and delegate",
    "src/personal_finance_etl/backend/types/batch_result.py": "refactor(legacy): deactivate types/batch_result and delegate",
    "src/personal_finance_etl/backend/types/pipeline.py": "refactor(legacy): deactivate types/pipeline and delegate",
    "src/personal_finance_etl/backend/types/analytics.py": "refactor(legacy): deactivate types/analytics and delegate",
    "src/personal_finance_etl/backend/utils/models.py": "refactor(legacy): deactivate models LogLevel and TaxLot",
    # Phase 2 Config & Common Primitives
    "src/personal_finance_etl/config/financial_rules/household.py": "refactor(config): implement household policy and budget rules",
    "src/personal_finance_etl/config/financial_rules/investments.py": "refactor(config): implement investment and portfolio rules",
    "src/personal_finance_etl/config/financial_rules/tax.py": "refactor(config): implement tax assumptions and rates policy",
    "src/personal_finance_etl/config/financial_rules/fire.py": "refactor(config): implement FIRE, CMA and Monte Carlo policy",
    "src/personal_finance_etl/config/financial_rules/model.py": "refactor(config): implement root FinancialRules composed model",
    "src/personal_finance_etl/config/financial_rules/__init__.py": "refactor(config): export financial rules policy models",
    "src/personal_finance_etl/config/settings.py": "refactor(config): implement Settings and FileHashPolicy models",
    "src/personal_finance_etl/config/__init__.py": "refactor(config): export Settings and FinancialRules",
    "src/personal_finance_etl/infrastructure/preferences/repository.py": "refactor(infrastructure): implement PreferencesManager store",
    "src/personal_finance_etl/infrastructure/preferences/__init__.py": "refactor(infrastructure): export PreferencesManager repository",
    "src/personal_finance_etl/infrastructure/filesystem/paths.py": "refactor(infrastructure): implement path and cache utilities",
    "src/personal_finance_etl/infrastructure/filesystem/__init__.py": "refactor(infrastructure): export filesystem path helpers",
    "src/personal_finance_etl/domain/common/identity.py": "refactor(domain/common): add deterministic entity identity v2",
    "src/personal_finance_etl/domain/common/dates.py": "refactor(domain/common): implement Indian fiscal year and dates",
    "src/personal_finance_etl/domain/common/polars.py": "refactor(domain/common): implement reusable analytical expressions",
    "src/personal_finance_etl/domain/common/__init__.py": "refactor(domain/common): export common domain primitives",
    "tests/test_phase2_config_and_primitives.py": "test(config): add Phase 2 configuration and primitives tests",
    # Phase 2 Legacy Deactivations
    "src/personal_finance_etl/backend/config/financial_rules.py": "refactor(legacy): deactivate config/financial_rules and delegate",
    "src/personal_finance_etl/backend/config/settings.py": "refactor(legacy): deactivate config/settings and delegate",
    "src/personal_finance_etl/backend/utils/helpers.py": "refactor(legacy): deactivate utils/helpers and delegate",
    "src/personal_finance_etl/backend/utils/identity.py": "refactor(legacy): deactivate utils/identity and delegate",
    "src/personal_finance_etl/backend/utils/polars_expressions.py": "refactor(legacy): deactivate utils/polars_expressions and delegate",
    "src/personal_finance_etl/backend/engines/tax/utils/date_utils.py": "refactor(legacy): deactivate engines/tax date_utils and delegate",
    # Phase 3 Infrastructure Contracts
    "src/personal_finance_etl/contracts/recovery.py": "refactor(contracts): update backup and restore result contracts",
    # Phase 3 Control Plane
    "src/personal_finance_etl/infrastructure/control_plane/__init__.py": "refactor(infrastructure): export control plane repositories",
    "src/personal_finance_etl/infrastructure/control_plane/connection.py": "refactor(infrastructure): implement SQLiteManager connection",
    "src/personal_finance_etl/infrastructure/control_plane/hashing.py": "refactor(infrastructure): implement hashing and file identity",
    "src/personal_finance_etl/infrastructure/control_plane/run_repository.py": "refactor(infrastructure): implement RunRepository lifecycle",
    "src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py": "refactor(infrastructure): implement ArtifactRepository store",
    "src/personal_finance_etl/infrastructure/control_plane/file_sync.py": "refactor(infrastructure): implement FileSyncService sync",
    "src/personal_finance_etl/infrastructure/control_plane/facade.py": "refactor(infrastructure): implement ControlPlane facade",
    # Phase 3 Warehouse Schemas
    "src/personal_finance_etl/infrastructure/warehouse/schema/__init__.py": "refactor(warehouse): export schema DDL statements and pragmas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/pragmas.py": "refactor(warehouse): define SQLite and DuckDB pragmas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/control_plane.py": "refactor(warehouse): define raw control plane DDL",
    "src/personal_finance_etl/infrastructure/warehouse/schema/bronze.py": "refactor(warehouse): define bronze lakehouse DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/silver.py": "refactor(warehouse): define silver layer DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/gold.py": "refactor(warehouse): define gold presentation DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/meta.py": "refactor(warehouse): define meta telemetry DDL schemas",
    # Phase 3 Warehouse & Storage
    "src/personal_finance_etl/infrastructure/warehouse/__init__.py": "refactor(warehouse): export warehouse layers and registry",
    "src/personal_finance_etl/infrastructure/warehouse/connection.py": "refactor(warehouse): implement DuckDBManager connection",
    "src/personal_finance_etl/infrastructure/warehouse/registry.py": "refactor(warehouse): implement data contract registries",
    "src/personal_finance_etl/infrastructure/warehouse/fingerprints.py": "refactor(warehouse): implement contract registry fingerprinting",
    "src/personal_finance_etl/infrastructure/warehouse/bronze.py": "refactor(warehouse): implement BronzeLayer delta upserts",
    "src/personal_finance_etl/infrastructure/warehouse/silver.py": "refactor(warehouse): implement SilverLayer table persistence",
    "src/personal_finance_etl/infrastructure/warehouse/gold.py": "refactor(warehouse): implement GoldLayer analytical tables",
    "src/personal_finance_etl/infrastructure/warehouse/meta.py": "refactor(warehouse): implement MetaLayer telemetry and healing",
    # Phase 3 Recovery & Logging
    "src/personal_finance_etl/infrastructure/recovery/__init__.py": "refactor(infrastructure): export SystemBackupManager",
    "src/personal_finance_etl/infrastructure/recovery/backup.py": "refactor(infrastructure): implement SystemBackupManager",
    "src/personal_finance_etl/infrastructure/logging/__init__.py": "refactor(infrastructure): export setup_logger and handlers",
    "src/personal_finance_etl/infrastructure/logging/setup.py": "refactor(infrastructure): implement multi-process logging",
    # Phase 3 Tests
    "tests/test_phase3_infrastructure.py": "test(infrastructure): add Phase 3 infrastructure test suite",
    # Phase 3 Legacy Deactivations
    "src/personal_finance_etl/backend/load/control_plane/__init__.py": "refactor(legacy): deactivate backend control plane init",
    "src/personal_finance_etl/backend/load/control_plane/connection.py": "refactor(legacy): deactivate load control plane connection",
    "src/personal_finance_etl/backend/load/control_plane/utils.py": "refactor(legacy): deactivate load control plane utils",
    "src/personal_finance_etl/backend/load/control_plane/run_repo.py": "refactor(legacy): deactivate load control plane run_repo",
    "src/personal_finance_etl/backend/load/control_plane/artifact_repo.py": "refactor(legacy): deactivate load control plane artifact_repo",
    "src/personal_finance_etl/backend/load/control_plane/file_sync.py": "refactor(legacy): deactivate load control plane file_sync",
    "src/personal_finance_etl/backend/load/control_plane/orchestrator.py": "refactor(legacy): deactivate control plane orchestrator",
    "src/personal_finance_etl/backend/load/schema/__init__.py": "refactor(legacy): deactivate backend load schema init",
    "src/personal_finance_etl/backend/load/schema/pragmas.py": "refactor(legacy): deactivate backend load schema pragmas",
    "src/personal_finance_etl/backend/load/schema/control_plane.py": "refactor(legacy): deactivate load schema control_plane",
    "src/personal_finance_etl/backend/load/schema/bronze.py": "refactor(legacy): deactivate backend load schema bronze",
    "src/personal_finance_etl/backend/load/schema/silver.py": "refactor(legacy): deactivate backend load schema silver",
    "src/personal_finance_etl/backend/load/schema/gold.py": "refactor(legacy): deactivate backend load schema gold",
    "src/personal_finance_etl/backend/load/schema/meta.py": "refactor(legacy): deactivate backend load schema meta",
    "src/personal_finance_etl/backend/load/database.py": "refactor(legacy): deactivate load database manager",
    "src/personal_finance_etl/backend/load/registry.py": "refactor(legacy): deactivate load contract registry",
    "src/personal_finance_etl/backend/load/bronze.py": "refactor(legacy): deactivate load bronze layer",
    "src/personal_finance_etl/backend/load/silver.py": "refactor(legacy): deactivate load silver layer",
    "src/personal_finance_etl/backend/load/gold.py": "refactor(legacy): deactivate load gold layer",
    "src/personal_finance_etl/backend/load/metadata.py": "refactor(legacy): deactivate load metadata layer",
    "src/personal_finance_etl/backend/load/backup.py": "refactor(legacy): deactivate load backup manager",
    "src/personal_finance_etl/backend/utils/logger.py": "refactor(legacy): deactivate utils logger setup",
    "src/personal_finance_etl/backend/utils/reproducibility.py": "refactor(legacy): deactivate utils reproducibility",
    # Scripts & Tooling
    "scripts/auto_commit.py": "chore(scripts): add auto_commit tool for granular commits",
}


def _infer_commit_message(filepath: str, status: str) -> str:
    """Infer a Commitlint-compliant message (max 72 chars) based on path heuristics."""
    norm = filepath.replace("\\", "/")
    if norm in KNOWN_COMMIT_MESSAGES:
        return KNOWN_COMMIT_MESSAGES[norm]

    # Package __init__.py skeleton declaration
    if norm.endswith("__init__.py"):
        pkg_parts = norm.split("/")
        pkg_name = pkg_parts[-2] if len(pkg_parts) >= 2 else "root"
        return f"refactor(arch): initialize {pkg_name} package boundary"

    # Test files
    if norm.startswith("tests/"):
        stem = Path(norm).stem.replace("test_", "")
        return f"test({stem[:15]}): update test suite"

    # Legacy backend deactivations
    if "backend/" in norm:
        stem = Path(norm).stem
        return f"refactor(legacy): deactivate {stem} and delegate"

    # Target architectural packages
    if norm.startswith("src/personal_finance_etl/"):
        rel = norm.replace("src/personal_finance_etl/", "")
        parts = rel.split("/")
        layer = parts[0]
        name = Path(norm).stem
        msg = f"refactor({layer}): implement {name}"
        if len(msg) > 72:
            msg = msg[:72]
        return msg

    # Documentation
    if norm.endswith(".md"):
        stem = Path(norm).stem
        return f"docs: update {stem[:30]} documentation"

    # Generic fallback
    stem = Path(norm).stem
    action = "add" if "?" in status or "A" in status else "update"
    return f"chore: {action} {stem[:40]}"


def get_changed_files() -> list[tuple[str, str]]:
    """Return list of (status, filepath) for all uncommitted files."""
    proc = subprocess.run(
        ["git", "status", "-s", "-uall"],
        capture_output=True,
        text=True,
        check=True,
    )
    results: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        status_part = line[:2].strip()
        file_part = line[2:].strip().strip('"')
        results.append((status_part, file_part))
    return results


def run_git_commit(filepath: str, message: str, dry_run: bool = False) -> bool:
    """Stage a single file and create a git commit."""
    # Commitlint enforcement: header must be <= 72 characters, lowercase
    if len(message) > 72:
        print(f"ERROR: Commit message exceeds 72 characters ({len(message)} chars): '{message}'")
        return False

    norm_path = filepath.replace("/", "\\") if sys.platform == "win32" else filepath

    if dry_run:
        print(f"[DRY-RUN] git add {norm_path}")
        print(f"[DRY-RUN] git commit -m \"{message}\" (len: {len(message)})")
        return True

    # 1. git add
    add_proc = subprocess.run(["git", "add", norm_path], capture_output=True, text=True)
    if add_proc.returncode != 0:
        print(f"FAILED git add {norm_path}: {add_proc.stderr}")
        return False

    # 2. git commit
    commit_proc = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
    if commit_proc.returncode != 0:
        print(f"FAILED git commit for {norm_path}: {commit_proc.stderr}")
        return False

    print(f"[OK] Committed {norm_path}: \"{message}\"")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit changes file-by-file following Commitlint standards.")
    parser.add_argument("--dry-run", action="store_true", help="Preview commits without executing git commands.")
    parser.add_argument("--run", action="store_true", help="Execute the commits immediately.")
    parser.add_argument("--file", type=str, help="Commit only a single specific file.")
    args = parser.parse_args()

    # Default to dry-run if neither --run nor --dry-run is passed
    is_dry_run = not args.run

    if args.file:
        files = [("M", args.file)]
    else:
        files = get_changed_files()

    if not files:
        print("Working tree is completely clean. Nothing to commit.")
        return 0

    mode_label = "DRY-RUN PREVIEW" if is_dry_run else "EXECUTING COMMITS"
    print(f"\n--- {mode_label} ({len(files)} files found) ---\n")

    success_count = 0
    fail_count = 0

    for status, filepath in files:
        message = _infer_commit_message(filepath, status)
        ok = run_git_commit(filepath, message, dry_run=is_dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print(f"\nDone: {success_count} succeeded, {fail_count} failed.")
    if is_dry_run:
        print("To execute these commits, run: uv run python scripts/auto_commit.py --run")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

