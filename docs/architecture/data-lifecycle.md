# Data Lifecycle

This document follows one source artifact from discovery to decision-ready analytical state.

The lifecycle is intentionally asymmetric:

> **Raw/Bronze preserve and synchronize evidence incrementally. Silver/Gold reconstruct derived financial state deterministically.**

That split is what lets the system handle a growing source history without making downstream finance depend on fragile incremental patches.

---

## 1. A run is an observable lifecycle, not a script

The Control Plane creates a durable run identity before the main analytical transaction:

```python
run_id = cp.runs.start_run(
    cfg_json=self.cfg.model_dump_json(),
    rules_json=self.rules.model_dump_json() if self.rules else None,
)
```

That call also snapshots Settings and FinancialRules by content hash.

The run initially exists as:

```text
STARTED
```

Then both local persistence transactions begin:

```python
self.db_manager.conn.execute("BEGIN TRANSACTION")
cp.begin_transaction()

cp.runs.update_run_status(run_id, "RUNNING")
```

A failed analytical run therefore still has an operational identity.

---

**Implementation:** `src/personal_finance_etl/backend/pipeline/etl_pipeline.py` (lines 248–273).

```python
    def run(self) -> None:
        self.cfg.validate_config()

        validate_registry()

        start_time = time.perf_counter()

        run_id = None
        cp = None
        log_file_path = self.db_manager.db_path.replace(".duckdb", ".log")

        try:
            add_queue_handler(cast("multiprocessing.Queue[Any]", self.status_queue))
            add_file_handler(log_file_path)

            logger.debug("=== ETL CONFIGURATION DUMP ===")
            if hasattr(self.cfg, "model_dump_json"):
                logger.debug(self.cfg.model_dump_json(indent=2))
            else:
                logger.debug(str(self.cfg))

            logger.debug("=== FINANCIAL RULES DUMP ===")
            if self.rules is not None and hasattr(self.rules, "model_dump_json"):
                logger.debug(self.rules.model_dump_json(indent=2))
            else:
                logger.debug(str(self.rules))
```

## 2. Discovery and artifact decisions

The orchestrator discovers statement files and then adds explicit configured sources:

```python
discovered_files = categorize_statement_files(
    self.cfg.STATEMENTS_FOLDER,
    strict=True,
)

discovered_files["sqlite_source"] = [
    SQLiteExtractor(self.cfg.SOURCE_DB_FOLDER).get_latest_sqlite_backup()
]
discovered_files["mf_isin"] = [self.cfg.MF_ISIN_CSV_PATH]
discovered_files["benchmark_mapping"] = [self.cfg.BENCHMARK_MAPPING_CSV_PATH]
discovered_files["opening_balances"] = [self.cfg.OPENING_BALANCE_CSV_PATH]
```

Discovery answers:

> **What source artifacts exist now?**

It does not answer:

> **Which ones need processing?**

That belongs to synchronization state.

---

**Implementation:** `src/personal_finance_etl/backend/load/control_plane/file_sync.py` (lines 30–67).

```python
    def sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:
        """Synchronize the scan as one atomic control-plane operation."""
        with self.artifact_repo.db.atomic():
            return self._sync_with_disk(discovered_files, hash_policy, full_replace_categories)

    def _sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:
        registry_with_status = self.artifact_repo.get_registry_with_status()
        registry: dict[str, tuple[str, str]] = {
            path: (digest, category)
            for path, (digest, category, _status) in registry_with_status.items()
        }

        hash_to_paths: dict[str, dict[str, list[str]]] = {}
        for path, (digest, category, status) in registry_with_status.items():
            if status != "REMOVED" and digest:
                hash_to_paths.setdefault(category, {}).setdefault(digest, []).append(path)

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}
        renames: list[tuple[str, str, str]] = []
        renamed_old_paths: set[str] = set()
        all_active_paths: set[str] = set()
        seen_path_categories: dict[str, str] = {}
        unique_input_count = 0
        full_replace = set(full_replace_categories)

        # Canonicalize/deduplicate before any destructive pruning. A path assigned to
        # multiple categories is a contract error and must not silently change identity.
```

## 3. Registry state and content fingerprints

`FileSyncService` compares discovered paths with the artifact registry:

```python
registry = self.artifact_repo.get_registry()

for category, filepaths in discovered_files.items():
    file_type = FILE_TYPE_MAP.get(category, "csv")
    should_check_hash = getattr(hash_policy, file_type, False)

    for filepath in filepaths:
        rel_path = filepath.replace("\\", "/")

        if rel_path not in registry:
            new_files[category].append(filepath)
        elif should_check_hash:
            disk_hash = compute_file_hash(filepath)
            if disk_hash != registry[rel_path]:
                changed_files[category].append(filepath)
```

This separates:

```text
discovered
from
actionable
```

With 1,608 artifacts in the production source environment, that distinction is fundamental.

---

**Implementation:** `src/personal_finance_etl/backend/load/control_plane/artifact_repo.py` (lines 237–271).

```python
    def _upsert_registry(
        self,
        *,
        filepath: str,
        filename: str,
        category: str,
        file_type: str,
        file_hash: str,
        file_size: int,
        now: str,
    ) -> tuple[str, str | None]:
        """Upsert metadata without assuming the persisted ID is path-derived."""
        path = normalize_path(filepath)
        existing = self.db.conn.execute(
            "SELECT file_id, sync_status FROM cp_file_registry WHERE relative_path = ?", (path,)
        ).fetchone()
        if existing:
            file_id, previous_status = existing
            self.db.conn.execute(
                """UPDATE cp_file_registry
                   SET file_name = ?, file_category = ?, file_type = ?, file_hash = ?,
                       file_size_bytes = ?, last_seen_run_id = COALESCE(?, last_seen_run_id), last_seen_at = ?,
                       last_changed_run_id = COALESCE(?, last_changed_run_id), last_changed_at = ?, sync_status = 'PENDING_BRONZE'
                   WHERE relative_path = ?""",
                (
                    filename,
                    category,
                    file_type,
                    file_hash,
                    file_size,
                    self.active_run_id,
                    now,
                    self.active_run_id,
                    now,
                    path,
```

## 4. Source bytes, history and retention

Actionable files are stored as binary evidence:

```python
with open(filepath, "rb") as file:
    raw_bytes = file.read()

self.db.conn.execute(
    """
    INSERT INTO cp_file_payloads (file_id, file_bytes)
    VALUES (?, ?)
    ON CONFLICT(file_id)
    DO UPDATE SET file_bytes = excluded.file_bytes
    """,
    (file_id, raw_bytes),
)
```

The registry stores:

```text
file_id
relative_path
category
physical type
SHA-256
size
first_ingested
last_ingested
sync_status
```

New or changed artifacts become:

```text
PENDING_BRONZE
```

**Implementation:** `src/personal_finance_etl/backend/load/control_plane/artifact_repo.py` (lines 301–334).

```python
    def ingest_binaries(
        self,
        actionable_files: dict[str, list[str]],
        new_files: dict[str, list[str]] | None = None,
        changed_files: dict[str, list[str]] | None = None,
    ) -> None:
        new_paths = {normalize_path(path) for paths in (new_files or {}).values() for path in paths}
        changed_paths = {
            normalize_path(path) for paths in (changed_files or {}).values() for path in paths
        }
        total_count = 0
        for category, filepaths in actionable_files.items():
            file_type = FILE_TYPE_MAP.get(category, "csv")
            for filepath in filepaths:
                path = normalize_path(filepath)
                try:
                    # Read once so the persisted bytes and their hash always describe the same content.
                    with open(filepath, "rb") as file_handle:
                        raw_bytes = file_handle.read()
                    digest = hash_bytes(raw_bytes)
                    size = len(raw_bytes)
                    now = self._now()
                    filename = os.path.basename(path)
                    with self.db.atomic():
                        file_id, previous_status = self._upsert_registry(
                            filepath=path,
                            filename=filename,
                            category=category,
                            file_type=file_type,
                            file_hash=digest,
                            file_size=size,
                            now=now,
                        )
                        self.db.conn.execute(
```

## 5. Bronze synchronization semantics

Bronze has two broad persistence behaviours.

### Historical/event sources

Replace only the partition owned by the changed source artifact:

```text
changed file
    ↓
delete old Bronze rows with that source identity
    ↓
insert replacement rows
    ↓
leave all unrelated history untouched
```

### Reference/current-state sources

Replace the complete current representation.

The code chooses that behaviour from `BronzeLayer.TABLE_MAPPINGS`.

This is more precise than describing Bronze as simply "incremental."

---

**Implementation:** `src/personal_finance_etl/backend/load/registry.py` (lines 15–37).

```python
@dataclass
class BronzeDataContract:
    """Defines the relationship between raw extraction attributes, control plane sync categories, and physical DuckDB tables."""

    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool


BRONZE_CONTRACT_REGISTRY: list[BronzeDataContract] = [
    BronzeDataContract("zcategory", "sqlite_source", "bronze.r_SQLite_ZCategory", True),
    BronzeDataContract("assetgroup", "sqlite_source", "bronze.r_SQLite_AssetGroup", True),
    BronzeDataContract("assets", "sqlite_source", "bronze.r_SQLite_Assets", True),
    BronzeDataContract("currency", "sqlite_source", "bronze.r_SQLite_Currency", True),
    BronzeDataContract("inoutcome", "sqlite_source", "bronze.r_SQLite_InOutcome", True),
    BronzeDataContract("stg_mf_isin_mapping", "mf_isin", "bronze.r_MF_ISIN_Mapping", True),
    BronzeDataContract(
        "stg_benchmark_mapping", "benchmark_mapping", "bronze.r_Benchmark_Mapping", True
    ),
    BronzeDataContract(
        "raw_opening_balances", "opening_balances", "bronze.r_Opening_Balances", True
    ),
```

## 6. Canonical transformations from complete evidence

The orchestrator passes complete Bronze into the transformation DAG:

```python
self._transform(full_dataset)
```

The DAG standardizes source-shaped data into canonical financial contracts.

This means downstream engines do not need to reason about:

```text
which files changed today?
```

They reason about:

```text
what is the complete current financial state?
```

That simplifies analytical correctness.

---

**Implementation:** `src/personal_finance_etl/backend/pipeline/core/transformer.py` (lines 1–33).

```python
import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.pipeline.strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
    USStockPipeline,
)
from personal_finance_etl.backend.transform.calendar import (
    get_stg_calendar_ref,
    transform_d_calendar,
)
from personal_finance_etl.backend.transform.dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
    transform_d_currency,
    transform_d_expense_category,
    transform_d_expense_subcategory,
    transform_d_income_category,
    transform_d_income_subcategory,
    transform_d_investment_benchmark_master,
    transform_d_macro_parameters,
)
from personal_finance_etl.backend.transform.facts import (
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
)
from personal_finance_etl.backend.transform.investments import (
```

## 7. Currency and dynamic evidence lifecycle

External benchmark data follows the same evidence philosophy even though it is not discovered as a normal local file.

Fetched history is serialized and injected as a virtual artifact.

The hardened identity convention is:

```text
virtual://<category>/<filename>
```

The virtual artifact receives:

- deterministic identity,
- SHA-256,
- payload bytes,
- synchronization state.

So external acquisition does not bypass provenance merely because it originated from an API/provider.

---

**Implementation:** `src/personal_finance_etl/backend/pipeline/currency_pipeline.py` (lines 1–35).

```python
import os
from datetime import date

import polars as pl

from personal_finance_etl.backend.extract.currency_extractor import CurrencyExtractor
from personal_finance_etl.backend.load.bronze import BronzeLayer
from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.transform.currency_transformer import transform_currency_fx_rates
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class CurrencyPipeline:
    def __init__(
        self, cp: ControlPlane, bronze: BronzeLayer, status_queue: ILogger, max_workers: int = 8
    ):
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue
        self.max_workers = max_workers

    def run(
        self,
        df_currency: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Runs the Currency FX pipeline."""

        logger.info("Phase 3.6: Dynamic Currency FX Extraction & Transformation...")
        logger.info(f"  -> Target Global Range: {global_start_date} to {global_end_date}")

        self.status_queue.put(
```

## 8. Quant, tax and presentation dependencies

The canonical frames feed:

```text
Investment Quant Engine
        +
Wealth Analytics Engine
```

The investment engine reconstructs:

- FIFO lots,
- realized/unrealized state,
- broker reconciliation,
- benchmark state,
- tax-aware values,
- cash-flow-aware returns.

The wealth engine reconstructs:

- household ledger,
- book/market/after-tax wealth,
- cash-flow reconciliation,
- budget/tax planning,
- FIRE.

The two engines meet through shared financial state.

---

**Implementation:** `src/personal_finance_etl/backend/pipeline/etl_pipeline.py` (lines 150–185).

```python
    def _run_engines(self, cp: "ControlPlane | None", run_id: str) -> None:

        logger.info("Starting Investment Quant Engine...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.6, level=LogLevel.STEP))

        quant_engine = InvestmentQuantEngine(
            df_p=self.dfs["df_f_tf_inv_purchase"],
            df_s=self.dfs["df_f_tf_inv_sale"],
            df_m=self.dfs["df_f_investment_market_data"],
            df_i=self.dfs["df_d_investment_master"],
            df_b=self.dfs["df_f_investment_benchmark_data"],
            df_t=self.dfs["df_d_macro_parameters"],
            df_fx=self.dfs.get("df_f_currency_fx_rates"),
            status_queue=self.status_queue,
            rules=self.rules,
            start_date=None,
            end_date=None,
            run_id=run_id,
        )
        analytics_results = quant_engine.run()
        self.dfs.update(analytics_results)
        lot_df = analytics_results.get("df_f_investment_analytics_lot", pl.DataFrame())
        if (
            not lot_df.is_empty()
            and "Quantity" in lot_df.columns
            and "Closing_Date" in lot_df.columns
        ):
            max_date = lot_df.select(pl.col("Closing_Date").max()).item()
            open_lots = lot_df.filter(
                (pl.col("Closing_Date") == max_date) & (pl.col("Quantity") > 0)
            ).height
        else:
            open_lots = 0

        logger.info(f"  -> Quant Engine mapped {open_lots} open tax lots across portfolio.")

```

## 9. Contract publication and run finalization

The serving layers are not incrementally patched:

```python
SilverLayer(self.db_manager).load(self.dfs)
GoldLayer(self.db_manager).load(self.dfs)
```

The lifecycle therefore ends with:

```text
complete Bronze
      ↓
complete canonical state
      ↓
complete analytical state
      ↓
replace Silver / Gold
```

This is a deliberate correctness trade-off.

Incrementalizing source history gives a large performance benefit.

Incrementalizing every financial dependency would add complexity where the current workload does not require it.

---

**Implementation:** `src/personal_finance_etl/backend/pipeline/etl_pipeline.py` (lines 400–432).

```python
            )

            self._process_currency(cp, bronze)
            self._process_us_market_data(cp, bronze)
            self._process_benchmark(cp, bronze)

            t_eng_start = time.perf_counter()
            logger.info("[PHASE] --- 4/5: Executing Advanced Analytics & Monte Carlo engines ---")
            self._run_engines(cp, str(run_id))

            # Strict DataContract Validation

            registered_contracts = {c.contract_id for c in DATA_CONTRACT_REGISTRY}
            for df_key in self.dfs.keys():
                if df_key not in registered_contracts:
                    raise RuntimeError(
                        f"Engine produced unregistered table '{df_key}'. All analytical tables must be defined in DATA_CONTRACT_REGISTRY."
                    )

            missing_contracts = registered_contracts - set(self.dfs.keys())
            if missing_contracts:
                raise RuntimeError(f"Engine failed to produce required tables: {missing_contracts}")

            logger.info(
                f"[PHASE] 4/5 Complete [{time.perf_counter() - t_eng_start:.2f}s] - Presentation logic built {len(self.dfs)} total tables."
            )

            # Load Phase (Silver & Gold)
            t_load_start = time.perf_counter()
            logger.info("[PHASE] --- 5/5: Fully replacing Silver and Gold analytical layers ---")
            SilverLayer(self.db_manager).load(self.dfs)
            GoldLayer(self.db_manager).load(self.dfs)
            logger.info(
```

## 10. Recovery and invariants

If DuckDB analytical state is lost or inconsistent while the Control Plane survives:

```text
Raw artifacts + payloads
        ↓
requeue missing Bronze state
        ↓
rebuild Bronze
        ↓
rebuild Silver
        ↓
rebuild Gold
```

`MetaLayer.heal_duckdb_registry()` compares Control Plane artifacts with DuckDB's current registry and returns missing analytical artifacts to `PENDING_BRONZE`.

The direction of authority is one-way:

```text
Control Plane → analytical recovery
```

not the reverse.

---

**Implementation:** `src/personal_finance_etl/backend/load/control_plane/connection.py` (lines 71–85).

```python
    def atomic(self) -> Generator[None]:
        """Atomic scope that works both standalone and nested in a pipeline transaction."""
        savepoint = f"cp_scope_{uuid.uuid4().hex}"
        self.conn.execute(f"SAVEPOINT {savepoint}")
        try:
            yield
            self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            try:
                self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            finally:
                self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise

    @property
```

## Integration and related specifications

- [System architecture](system-architecture.md)
- [Artifact lifecycle](control-plane-artifact-lifecycle.md)
- [Identity and replay](deterministic-identity-and-replay.md)
- [Backup and restore](backup-and-restore.md)

