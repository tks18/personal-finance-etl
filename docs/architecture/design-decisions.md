# Design Decisions

This page documents the architectural choices that are easiest to misunderstand when viewed only from the final code.

The pattern is:

```text
Problem
→ decision
→ production evidence
→ benefit
→ trade-off
```

These are not claims that the chosen architecture is universally superior.

They are the choices that fit this workload.

---

## 1. Operational history in SQLite

### Problem

The system needs durable local ownership of:

- raw evidence,
- artifact identity,
- hashes,
- synchronization state,
- runs,
- failures,
- configuration provenance,
- execution logs.

This is operational state, not analytical fact modelling.

### Decision

Use SQLite as the authoritative Control Plane.

### Production evidence

```python
class ControlPlane:
    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db = SQLiteManager(base_path, db_name)
        self.artifacts = ArtifactRepository(self.db)
        self.runs = RunRepository(self.db)
        self.file_sync = FileSyncService(self.artifacts)
```

### Benefit

One local transactional system owns operational truth.

### Trade-off

The application now coordinates two databases.

**Implementation:** `src/personal_finance_etl/backend/load/control_plane/connection.py` (lines 13–52).

```python
class SQLiteManager:
    """SQLite connection owner for the durable ETL control plane."""

    SCHEMA_VERSION = 2

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db_path = os.path.join(base_path or ".", db_name)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteManager connection not opened.")
        return self._conn

    def open(self) -> None:
        if self._conn is not None:
            return
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        logger.debug("[DATABASE:SQLITE] Opening connection to %s", self.db_path)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None,
            )
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.execute("PRAGMA busy_timeout = 30000;")
            connection.execute("PRAGMA journal_mode = WAL;")
            connection.execute("PRAGMA synchronous = NORMAL;")
            connection.execute("PRAGMA cache_size = -64000;")
            connection.execute("PRAGMA mmap_size = 2147483648;")
            connection.execute("PRAGMA temp_store = MEMORY;")
            if connection.execute("PRAGMA foreign_keys;").fetchone()[0] != 1:
                raise RuntimeError("SQLite foreign-key enforcement could not be enabled.")
            self._conn = connection
        except Exception:
            if connection is not None:
```

## 2. Analytical state in DuckDB

### Problem

The system needs persistent local columnar analytics, SQL inspection, fast rebuilds, and Power BI serving.

### Decision

Use one embedded DuckDB file for:

```text
Bronze
Silver
Gold
Meta
```

### Production evidence

```python
self._conn = duckdb.connect(self.db_path)

self._conn.execute(
    f"PRAGMA memory_limit='{mem_gb}GB'"
)
self._conn.execute("PRAGMA threads=4")
```

### Benefit

No database server is required for a single-user analytical workload.

### Trade-off

This is not designed as a multi-user transactional warehouse.

That is acceptable because the workload is local-first by design.

---

**Implementation:** `src/personal_finance_etl/backend/load/database.py` (lines 1–40).

```python
import os

import duckdb
import psutil

from personal_finance_etl.backend.load.schema.gold import GOLD_DDL
from personal_finance_etl.backend.load.schema.meta import META_DDL
from personal_finance_etl.backend.load.schema.silver import SILVER_DDL
from personal_finance_etl.backend.utils.logger import logger


class DuckDBManager:
    """Owns the single persistent DuckDB file and its long-lived connection."""

    def __init__(self, base_path: str, db_name: str = "Personal_Finance_DB.duckdb"):
        self.base_path = base_path
        self.db_path = os.path.join(base_path, db_name)
        os.makedirs(base_path, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Returns the active connection. Raises if not opened."""
        if self._conn is None:
            raise RuntimeError("DuckDBManager.open() must be called before accessing conn.")
        return self._conn

    def open(self) -> duckdb.DuckDBPyConnection:
        """Opens the single long-lived connection. Called once at pipeline start."""
        if self._conn is not None:
            return self._conn
        logger.debug(f"[DATABASE:DUCKDB] Opening connection to {self.db_path}")
        self._conn = duckdb.connect(self.db_path)
        mem_gb = max(4, int(psutil.virtual_memory().total / (1024**3) * 0.75))
        self._conn.execute(f"PRAGMA memory_limit='{mem_gb}GB'")
        self._conn.execute("PRAGMA threads=4")
        logger.debug(f"[DATABASE:DUCKDB] Connection configured: memory_limit={mem_gb}GB, threads=4")
        return self._conn

    def close(self) -> None:
```

## 3. Distinct authority boundaries

### Problem

Before the Control Plane existed, Meta naturally accumulated responsibilities because DuckDB was the only database.

Once durable raw state was introduced, that ownership became ambiguous.

### Decision

Move historical operational authority into SQLite and keep DuckDB Meta lean.

```mermaid
flowchart LR
    CP["SQLite<br/>Historical Operational Truth"] -. projection .-> META["DuckDB Meta<br/>Current Analytical Context"]
```

### Benefit

There is one answer to:

> Which system owns run history?

SQLite.

### Trade-off

Operational-history queries no longer live beside analytical marts in one database.

That is a good trade for clearer ownership.

---

**Implementation:** `src/personal_finance_etl/backend/load/metadata.py` (lines 1–38).

```python
import os

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.load.control_plane.orchestrator import ControlPlane
from personal_finance_etl.backend.load.control_plane.utils import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
)
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.reproducibility import (
    generate_contract_registry_fingerprint,
)


class MetaLayer:
    """
    Manages all DuckDB analytical telemetry schemas.
    Maintains a strictly lean, "current-state" snapshot of the Lakehouse.
    Run tracking and historical lineages are deferred to the SQLite ControlPlane.
    """

    def __init__(self, db_manager: DuckDBManager, cfg: Settings, rules: FinancialRules | None):
        self.db_manager = db_manager
        self.cfg = cfg
        self.rules = rules
        self.conn = self.db_manager.conn

    def heal_duckdb_registry(self, cp: "ControlPlane") -> None:
        """Self-heals DuckDB file registry if items in SQLite control plane are missing."""
```

## 4. Retaining raw source evidence

### Problem

A filesystem path can disappear or mutate after ingestion.

### Decision

Persist actionable source bytes in `cp_file_payloads`.

```sql
CREATE TABLE IF NOT EXISTS cp_file_payloads (
    file_id TEXT PRIMARY KEY,
    file_bytes BLOB,
    FOREIGN KEY(file_id)
        REFERENCES cp_file_registry(file_id)
        ON DELETE CASCADE
);
```

### Benefit

Raw evidence survives independently from source-folder availability.

### Trade-off

Storage is duplicated.

For personal financial evidence, recoverability is worth more to me than minimizing disk usage.

---

**Implementation:** `src/personal_finance_etl/backend/load/control_plane/artifact_repo.py` (lines 301–333).

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
```

## 5. Rebuilding canonical financial state

### Problem

The production source population is large and continuously growing:

```text
1,608 artifacts as of 24 Sep 2026
+ ~2 broker snapshots/day
```

Reparsing everything every run wastes work.

But incremental propagation through every downstream financial dependency increases correctness complexity.

### Decision

Use:

```text
incremental Raw/Bronze
+
deterministic Silver/Gold rebuild
```

### Benefit

The expensive/growing source side is incrementalized while downstream financial state remains simple to reason about.

### Trade-off

Derived analytics recompute every run.

At the current workload, the full pipeline still completes in roughly **14–17 seconds**, so the correctness trade remains attractive.

---

**Implementation:** `src/personal_finance_etl/backend/load/silver.py` (lines 1–44).

```python
import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.backend.load.schema.silver import SILVER_DDL
from personal_finance_etl.backend.utils.logger import logger


class SilverLayer:
    """Full-replace layer for engine-computed analytics and reference data."""

    def __init__(self, db_manager: DuckDBManager):
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        if df.height == 0:
            return 0

        # Clean empty strings into true nulls only for dimension tables
        if "d_" in table_name:
            string_cols = [
                c
                for c, d in zip(df.columns, df.dtypes, strict=True)
                if d in (getattr(pl, "Utf8", None), getattr(pl, "String", None))
            ]
            if string_cols:
                df = df.with_columns(
                    [
                        pl.when(pl.col(c) == "").then(None).otherwise(pl.col(c)).alias(c)
                        for c in string_cols
                    ]
                )

        if table_name == "silver.d_Investment_Master":
            critical_errors: list[str] = []
            if "ISIN" in df.columns:
                missing_isin = df.filter(pl.col("ISIN").is_null())
                if missing_isin.height > 0:
                    logger.error(
                        f"CRITICAL: Found {missing_isin.height} rows with missing ISIN in d_Investment_Master."
                    )
```

## 6. Source-dependent Bronze replacement

### Problem

Not all sources mean the same thing.

A daily broker snapshot is historical evidence.

A current mapping/master can represent only the latest valid reference state.

### Decision

Support both:

```text
file-aware historical replacement
and
full replacement
```

### Benefit

Persistence semantics match source semantics.

### Trade-off

Bronze loading is slightly more complex than one universal append strategy.

That complexity is justified because the alternatives would either duplicate history or destroy it.

---

**Implementation:** `src/personal_finance_etl/backend/load/registry.py` (lines 15–45).

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
    BronzeDataContract(
        "raw_benchmark_master", "benchmark_master", "bronze.r_Benchmark_Master", True
    ),
    BronzeDataContract(
        "raw_macro_parameters", "macro_parameters", "bronze.r_Macro_Parameters", True
    ),
    BronzeDataContract("column_master", "column_master", "bronze.r_Column_Master", True),
    BronzeDataContract("mf_market_data_raw", "mf_holdings", "bronze.r_MF_Market_Data", False),
```

## 7. Polars and stateful Quant

### Problem

The pipeline performs many composable transformations and presentation calculations.

### Decision

Use Polars LazyFrames where transformations can remain declarative.

Independent presentation graphs are collected together:

```python
results = pl.collect_all(
    lazy_frames,
    engine="streaming",
)
```

### Benefit

Vectorized expressions, optimizer visibility, streaming execution, and reduced Python row iteration.

### Trade-off

Lazy execution can make debugging less immediate than eager step-by-step dataframes.

I materialize at persistence/algorithm boundaries where explicit state matters.

---

**Implementation:** `src/personal_finance_etl/backend/engines/analytics/engine.py` (lines 16–55).

```python
class InvestmentQuantEngine:
    """
    Orchestrates the quantitative engine pipeline.
    """

    def __init__(
        self,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame,
        df_b: pl.DataFrame | None,
        df_t: pl.DataFrame,
        df_fx: pl.DataFrame | None = None,
        status_queue: ILogger | None = None,
        rules: "FinancialRules | None" = None,
        start_date: date | None = None,
        end_date: date | None = None,
        run_id: str = "UNKNOWN",
    ):
        self.df_p = df_p
        self.df_s = df_s
        self.df_m = df_m
        self.df_i = df_i
        self.df_b = df_b if df_b is not None else pl.DataFrame()
        self.df_t = df_t
        self.df_fx = df_fx if df_fx is not None else pl.DataFrame()
        self.status_queue = status_queue
        self.rules = rules
        self.start_date = start_date
        self.end_date = end_date
        self.run_id = run_id

    def run(self) -> dict[str, pl.DataFrame]:
        try:
            return self._run()
        except Exception as e:
            if self.status_queue is not None:
                self.status_queue.put(
                    EngineStatus(
```

## 8. Deterministic financial identity

**Implementation:** `src/personal_finance_etl/backend/utils/identity.py` (lines 63–89).

```python
def _ordered_identity_fields(namespace: str, fields: dict[str, Any]) -> list[tuple[str, Any]]:
    """Return identity fields in a contract-defined, caller-order-independent order."""
    keys = set(fields)
    for field_order in _IDENTITY_FIELD_ORDERS.get(namespace, ()):
        if keys == set(field_order):
            return [(key, fields[key]) for key in field_order]

    # Unknown/new contracts remain deterministic rather than inheriting insertion
    # order. Add a namespace contract above if its field order must be semantic.
    return [(key, fields[key]) for key in sorted(fields)]


def generate_deterministic_id(namespace: str, fields: dict[str, Any]) -> str:
    """Generate a stable deterministic ID using Canonical ID Serialization v2.

    Known namespaces retain their established field order and hashes. New or
    changed field sets use sorted keys until an explicit order is registered.
    """
    pairs = [
        [canonicalize_value(key), canonicalize_value(value)]
        for key, value in _ordered_identity_fields(namespace, fields)
    ]
    payload = json.dumps(
        [namespace, "v2", pairs], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    hash_str = hashlib.sha256(payload).hexdigest()
    return f"{namespace}_{hash_str[:16]}"
```

## 9. Configuration and reproducibility

### Problem

A run needs reproducibility context, but copying the same configuration payload every run creates unnecessary duplication.

### Decision

Hash canonical Settings and FinancialRules payloads.

```python
rules_hash = hashlib.sha256(
    rules_json.encode("utf-8")
).hexdigest()

rules_id = f"snap_rule_{rules_hash[:12]}"
```

### Benefit

Identical policy maps to identical snapshot identity.

### Trade-off

The snapshot proves configuration identity, not full historical replay if code/schema later changes.

---

**Implementation:** `src/personal_finance_etl/backend/utils/reproducibility.py` (lines 9–48).

```python
def generate_contract_registry_fingerprint(tables_metadata: list[dict[str, Any]]) -> str:
    """
    Computes a deterministic fingerprint of the active table grains and publishers.
    Avoids using a manual registry version counter by hashing the actual structural metadata.
    """
    sorted_metadata = sorted(tables_metadata, key=lambda x: str(x.get("table_name", "")))
    payload = json.dumps(sorted_metadata, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_reproducibility_envelope(
    input_fingerprint: str,
    rules_hash: str,
    macro_settings_hash: str,
    registry_fingerprint: str,
    root_seed: str,
    model_version: str,
) -> dict[str, str]:
    """
    Ties the inputs, rules, macro settings, registry, and seed into the final unified envelope.
    This guarantees that if the envelope hash matches, the simulation is mathematically guaranteed
    to reproduce the exact same Monte Carlo distributions and projections.
    """
    envelope_data = {
        "input_fingerprint": input_fingerprint,
        "rules_hash": rules_hash,
        "macro_settings_hash": macro_settings_hash,
        "registry_fingerprint": registry_fingerprint,
        "root_seed": root_seed,
        "model_version": model_version,
    }
    envelope_payload = json.dumps(envelope_data, sort_keys=True).encode("utf-8")
    envelope_hash = hashlib.sha256(envelope_payload).hexdigest()

    return {
        "envelope_hash": envelope_hash,
        **envelope_data,
    }


```

## 10. Coordinated recovery

**Implementation:** `src/personal_finance_etl/backend/load/backup.py` (lines 17–57).

```python
class SystemBackupManager:
    """Coordinate SQLite Control Plane and DuckDB state as one recovery unit."""

    def __init__(
        self,
        base_path: str,
        sqlite_db_name: str = "Raw_Documents.sqlite",
        duckdb_name: str = "Personal_Finance_DB.duckdb",
    ):
        self.base_path = base_path
        self.sqlite_path = os.path.join(base_path, sqlite_db_name)
        self.duckdb_path = os.path.join(base_path, duckdb_name)
        self.backup_dir = os.path.join(base_path, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    @staticmethod
    def _checkpoint_duckdb(db_path: str) -> None:
        """Flush committed DuckDB state before a filesystem-level snapshot."""

        connection = duckdb.connect(db_path)
        try:
            connection.execute("CHECKPOINT")
        finally:
            connection.close()

    @staticmethod
    def _validate_sqlite(db_path: str) -> None:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError(f"Snapshot SQLite integrity check failed: {result!r}")
        finally:
            connection.close()

    @classmethod
    def _validate_duckdb(cls, db_path: str) -> None:
        """Open and checkpoint an extracted copy before production files are touched."""
        cls._checkpoint_duckdb(db_path)

    def create_snapshot(self) -> str | None:
```

## Integration and related specifications

- [System architecture](system-architecture.md)
- [Artifact lifecycle](control-plane-artifact-lifecycle.md)
- [Identity and replay](deterministic-identity-and-replay.md)
- [Backup and restore](backup-and-restore.md)

