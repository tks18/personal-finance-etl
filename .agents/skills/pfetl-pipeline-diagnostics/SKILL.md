---
name: pfetl-pipeline-diagnostics
description: >-
  Use this skill when running headless pipeline profiles, troubleshooting DuckDB Medallion layers,
  inspecting SQLite Control Plane artifact synchronization, verifying deterministic ID stability,
  or diagnosing FIFO and tax calculation discrepancies.
---

# PFETL Pipeline Diagnostics & Headless Troubleshooting Runbook

This skill provides step-by-step procedures for profiling, inspecting, and diagnosing the personal finance ETL engine, its dual-database storage layers (DuckDB and SQLite), and its analytical pipelines.

---

## 1. Running Headless Pipeline Executions

Headless runs allow testing the full ETL pipeline without launching the CustomTkinter GUI.

### Configuration (`tests/config.toml`)
Ensure the test configuration points to either fixture statements or local data:

```toml
SOURCE_DB_FOLDER = "outputs/SOURCE_DB.db"
TARGET_DB_BASE_PATH = "outputs"

# Raw Store Config
ENABLE_RAW_DOCUMENT_STORE = true
RAW_DOCUMENT_STORE_NAME = "Raw_Documents.sqlite"
FORCE_REBUILD_RAW_STORE = false

# Dependencies
COLUMN_MASTER_PATH = "inputs/COLUMN_MASTER.csv"
MF_ISIN_CSV_PATH = "inputs/MF_ISIN_MAPPING.csv"
BENCHMARK_MAPPING_CSV_PATH = "inputs/BENCHMARK_MAPPING.csv"
BENCHMARK_MASTER_CSV_PATH = "inputs/BENCHMARK_MASTER.csv"
TAX_RATES_CSV_PATH = "inputs/TAX_RATES.csv"
OPENING_BALANCE_CSV_PATH = "inputs/OPENING_BALANCE.csv"
INFLATION_RATES_CSV_PATH = "inputs/INFLATION_RATES.csv"

# Statements
STATEMENTS_FOLDER = "inputs/Statements"
```

### Execution Command
Run the headless pipeline via `uv`:

```powershell
uv run python tests/run_headless.py
```

### Programmatic Headless Invocation (Custom Script)
To inspect execution with active event observation in a one-off Python script:

```python
import queue
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.infrastructure.observability import get_global_emitter

class StatusQueue:
    def __init__(self):
        self._q = queue.Queue()
    def put(self, event, block=True, timeout=None):
        print(f"[{getattr(event, 'severity', 'INFO')}] {getattr(event, 'message', event)}")

cfg = Settings.from_toml("tests/config.toml")
rules = FinancialRules.from_toml("tests/financial_rules.toml")
q = StatusQueue()

orchestrator = ETLOrchestrator(cfg, status_queue=q, rules=rules)
orchestrator.run()
```

---

## 2. Inspecting DuckDB Medallion Layers

The analytical warehouse is located at `<TARGET_DB_BASE_PATH>/Shan_Finance.duckdb` (or as configured in `Settings.TARGET_DB_NAME`).

### Medallion Schema Layout
- `bronze`: Source-shaped raw canonical evidence (`bronze.bank_transactions`, `bronze.equity_trades`, etc.).
- `silver`: Reconstructed financial state (`silver.standardized_trades`, `silver.normalized_cashflows`).
- `gold`: Decision-ready analytical surfaces (`gold.fifo_tax_lots`, `gold.realized_capital_gains`, `gold.net_worth_history`, `gold.fire_projection`).
- `meta`: Data contract fingerprints, run manifests, and schema lineage.

### Quick Inspection via Python Shell
```powershell
uv run python -c "
import duckdb
con = duckdb.connect('outputs/Shan_Finance.duckdb', read_only=True)
print('=== Schemas ===')
print(con.execute('SHOW SCHEMAS').fetchall())
print('\n=== Gold Tables ===')
print(con.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='gold'\").fetchall())
con.close()
"
```

---

## 3. SQLite Control Plane & Artifact Sync Diagnostics

The Control Plane manages raw document storage, file hashes, and run tracking in `Raw_Documents.sqlite`.

### Inspecting Sync Status and File Hashes
```powershell
uv run python -c "
import sqlite3
con = sqlite3.connect('outputs/Raw_Documents.sqlite')
cur = con.cursor()
print('=== Recent Runs ===')
for row in cur.execute('SELECT run_id, status, started_at, completed_at FROM run_metadata ORDER BY started_at DESC LIMIT 5'):
    print(row)
print('\n=== File Hash Summary ===')
cur.execute('SELECT category, count(*) FROM file_hash_registry GROUP BY category')
for row in cur.fetchall():
    print(row)
con.close()
"
```

### Sync Summary Record Metrics
When reviewing run sync state, verify:
- `actionable_count`: Total valid evidence statements discovered.
- `synced_count`: Statements with new or unchanged hashes loaded to Bronze.
- `healed_count`: Corrupted or re-hashed files recovered.
- `failed_count`: Files rejected due to extraction errors.

---

## 4. Deterministic Identity Verification

All financial record IDs must remain byte-stable across identical runs:

| ID Type | Invariant Components |
|---|---|
| `PURCHASE` / `SALE` | Account, ISIN, Trade Date, Units, Execution Price. |
| `LOT` | Acquisition Account, ISIN, Lot Open Date, Lot Index. |
| `REALIZED` | Sale ID + Matched Lot ID combination. |
| `TAX` | Assessment Year + Section + Tax Event Hash. |

To check if an algorithm change broke ID stability, compare Gold lots between two runs:
```python
# Verify byte stability between runs
assert lot_id_run_1 == lot_id_run_2
```

---

## 5. Transaction Split-Commit & Recovery

Commit order invariant:
1. **DuckDB commits first.**
2. **SQLite commits second.**

If a failure occurs between step 1 and step 2, the run enters `CommitState.RECOVERY_REQUIRED`.
To restore consistency:
```python
from personal_finance_etl.application.recovery import RestoreCoordinator
from personal_finance_etl.bootstrap.container import ServiceContainer

container = ServiceContainer()
backup_mgr = container.create_backup_manager(cfg)
# Restore from latest verified snapshot
backup_mgr.restore_latest_snapshot()
```
