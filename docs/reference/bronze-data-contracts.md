# Bronze Data Contracts

Bronze is the persistent source-shaped analytical boundary between durable raw evidence and canonical financial reconstruction.

The current layer is governed by `BRONZE_CONTRACT_REGISTRY`.

```python
@dataclass
class BronzeDataContract:
    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool
```

There are exactly **16 Bronze contracts** in v6.5.3.

The registry is executable architecture: it connects extraction output, Control Plane sync categories, physical DuckDB tables, replacement semantics, self-healing, Meta publication, and orphan cleanup.

---

## Contract model

A Bronze contract answers four questions:

| Field | Meaning |
| --- | --- |
| `extraction_attribute` | Attribute on the extraction result carrying the source-shaped frame |
| `sync_category` | Control Plane artifact category governing synchronization |
| `physical_table` | DuckDB Bronze table |
| `is_full_replace` | Whether each synchronization replaces the whole table or only artifact-owned history |

The two replacement modes are:

```text
is_full_replace = True
→ current/reference state
→ replace complete Bronze table

is_full_replace = False
→ historical/file-owned state
→ replace only rows owned by actionable source artifact
```

Historical tables retain `__file_name__` ownership so one changed artifact can replace its own partition without rebuilding all synchronized history.

---

## Contract catalog

| Extraction attribute | Sync category | Physical table | Replacement |
| --- | --- | --- | --- |
| `zcategory` | `sqlite_source` | `bronze.r_SQLite_ZCategory` | Full replace |
| `assetgroup` | `sqlite_source` | `bronze.r_SQLite_AssetGroup` | Full replace |
| `assets` | `sqlite_source` | `bronze.r_SQLite_Assets` | Full replace |
| `currency` | `sqlite_source` | `bronze.r_SQLite_Currency` | Full replace |
| `inoutcome` | `sqlite_source` | `bronze.r_SQLite_InOutcome` | Full replace |
| `stg_mf_isin_mapping` | `mf_isin` | `bronze.r_MF_ISIN_Mapping` | Full replace |
| `stg_benchmark_mapping` | `benchmark_mapping` | `bronze.r_Benchmark_Mapping` | Full replace |
| `raw_opening_balances` | `opening_balances` | `bronze.r_Opening_Balances` | Full replace |
| `raw_benchmark_master` | `benchmark_master` | `bronze.r_Benchmark_Master` | Full replace |
| `raw_macro_parameters` | `macro_parameters` | `bronze.r_Macro_Parameters` | Full replace |
| `column_master` | `column_master` | `bronze.r_Column_Master` | Full replace |
| `mf_market_data_raw` | `mf_holdings` | `bronze.r_MF_Market_Data` | File-owned historical |
| `mf_transactions_raw` | `mf_orders` | `bronze.r_MF_Transactions` | File-owned historical |
| `stock_market_data_raw` | `stock_pl` | `bronze.r_Stock_Market_Data` | File-owned historical |
| `stock_transactions_raw` | `stock_orders` | `bronze.r_Stock_Transactions` | File-owned historical |
| `benchmark_history_raw` | `benchmark_history` | `bronze.r_Benchmark_Data` | File-owned historical |

That gives:

```text
11 full-replace contracts
5 file-owned historical contracts
=
16 Bronze contracts
```

---

## Synchronization lifecycle

Artifact state is owned by the SQLite Control Plane.

```text
discovered / changed
        ↓
PENDING_BRONZE
        ↓
extract actionable evidence
        ↓
apply Bronze replacement semantics
        ↓
register current analytical identity in Meta
        ↓
SYNCED
```

`SYNCED` means the artifact completed Bronze synchronization. It is not an irreversible claim.

---

## Full-replace contracts

Full-replace contracts represent current/reference state.

For these contracts, Bronze synchronization replaces the complete table.

Examples include:

```text
SQLite reference state
ISIN mapping
benchmark mapping
opening balances
benchmark master
macro parameters
column master
```

The replacement boundary is the dataset, not the individual source file.

---

## File-owned historical contracts

Historical contracts preserve synchronized history across source artifacts.

Rows retain source ownership through:

```text
__file_name__
```

A changed artifact follows:

```text
delete old rows owned by artifact
        ↓
insert current artifact rows
```

If the current artifact produces zero rows, the delete still occurs. That prevents stale historical state from surviving when a previously non-empty source becomes empty.

---

## Self-healing

Bronze participates in active consistency checking.

For each artifact the Control Plane considers `SYNCED`, the Meta layer checks:

```text
Meta registry identity exists?
        ↓
required Bronze table exists?
        ↓
historical contract:
expected __file_name__ partition exists?
```

If required analytical state is missing:

```text
SYNCED
→ PENDING_BRONZE
```

The next normal run merges pending artifacts with new and changed artifacts and replays the same Bronze synchronization path.

Recovery therefore uses production ingestion semantics rather than a separate repair loader.

---

## Rename semantics

Artifact identity is path-derived.

A pure rename therefore migrates identity across:

```text
Control Plane registry
raw payload foreign key
Bronze __file_name__ ownership
DuckDB Meta registry
```

The underlying financial evidence does not become new merely because its path changed.

---

## Meta projection

`meta.m_Data_Contracts` publishes Bronze contracts alongside Silver and Gold.

For Bronze, the current Meta projection uses:

```text
contract_id
→ extraction_attribute

layer
→ bronze

domain
→ Raw

grain
→ File

producer
→ ControlPlane

is_full_replace
→ BronzeDataContract.is_full_replace

publication_order
→ 0
```

This is a current contract projection. It does not attempt to describe the deeper financial grain of source rows.

---

## Registry validation

`validate_registry()` verifies the Bronze registry before analytical execution.

The current invariants include:

```text
extraction_attribute is non-empty
sync_category is non-empty
physical_table is non-empty
physical Bronze tables are unique
contract count = 16
```

Silver and Gold have their own validation in the same registry module.

---

## Bronze design rules

1. Raw evidence and Bronze state are different durability boundaries.
2. Every persisted Bronze source has one registry contract.
3. Replacement semantics are explicit.
4. Historical replacement is artifact-owned.
5. Empty changed sources remove stale owned state.
6. `SYNCED` is challengeable by self-healing.
7. Recovery reuses normal ingestion.
8. Rename changes identity, not financial evidence.
9. Bronze remains source-shaped; canonical financial meaning begins downstream.
10. Meta reflects the contract registry rather than rediscovering it from table names.

---

## Related documentation

- [Data Lifecycle](../architecture/data-lifecycle.md)
- [Warehouse Architecture](../architecture/warehouse-architecture.md)
- [Meta & Control Plane Contracts](meta-data-contracts.md)
- [Silver Data Contracts](silver-data-contracts.md)
- [Adding a Data Source](../developer/adding-data-sources.md)

[← Reference Home](README.md) · [← Documentation Home](../README.md)
