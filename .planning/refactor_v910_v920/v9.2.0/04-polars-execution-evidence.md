# v9.2.0 — Polars Execution Evidence & Materialization Audit

## Materialization Operations Inventory

| Operation | Count |
| --- | ---: |
| `.collect()` | 27 |
| `.to_dicts()` | 30 |
| `collect_schema()` | 17 |
| `.rows()` | 1 |
| `iter_rows()` | 1 |
| `to_pandas()` | 0 |
| **Total** | **76** |

Calls occur across 29 files.

## Phase 4 Taxonomy Classification

Every one of the 76 materialization and conversion boundaries has been classified in [05-materialization-map.csv](05-materialization-map.csv):

| Taxonomy Category | Count | Strategic Treatment |
| --- | ---: | --- |
| `VALIDATION_DIAGNOSTIC` | 19 | **Preserve.** Lazy evaluation with `.limit(10).collect()` only executed upon failure for error messaging. |
| `SCHEMA_INSPECTION` | 17 | **Preserve.** Zero-data cost schema checking (`.collect_schema()`) without materializing memory rows. |
| `STATEFUL_ALGORITHM_BOUNDARY` | 17 | **Preserve.** Invariant requirement for sequential FIFO lot matching, forward-fill FX, and date caching. |
| `PUBLICATION_BOUNDARY` | 7 | **Preserve.** Terminal stages materializing data for DuckDB lakehouse insertion or silver/gold parquet writes. |
| `THIRD_PARTY_BOUNDARY` | 6 | **Preserve.** Boundary requirements for SQLite parameter binding and external yfinance requests. |
| `SCALAR_EXTRACTION` | 3 | **Preserve.** Single scalar value retrieval (CPI index value, row counts for telemetry). |
| `PROCESS_BOUNDARY` | 1 | **Preserve.** Explicit runtime `gc.collect()` between execution phases. |
| `UNNECESSARY` | 6 | **Target for Removal in Phase 5.** Redundant `.collect().lazy()` conversions that add round-trip overhead. |

## Unnecessary Boundaries Targeted for Phase 5 Elimination

1. `src/personal_finance_etl/application/investments/aggregation_service.py` (Line 396):
   - Redundant `.collect().lazy()` in group aggregation join.
2. `src/personal_finance_etl/infrastructure/providers/files/sqlite.py` (Lines 98–102):
   - Five redundant `.collect().lazy()` calls on `zcategory_lazy`, `assetgroup_lazy`, `assets_lazy`, `currency_lazy`, and `inoutcome_lazy` that eagerly materialize data already loaded in-memory from SQLite.
