# v9.2.0 — Polars Execution Evidence & Materialization Audit

## Materialization Operations Inventory

| Operation | Baseline | Post Phase 5 | Delta |
| --- | ---: | ---: | ---: |
| `.collect()` | 27 | 21 | -6 |
| `.to_dicts()` | 30 | 30 | 0 |
| `collect_schema()` | 17 | 17 | 0 |
| `.rows()` | 1 | 1 | 0 |
| `iter_rows()` | 1 | 1 | 0 |
| `to_pandas()` | 0 | 0 | 0 |
| **Total** | **76** | **70** | **-6** |

Calls occur across 29 files.

## Materialization Taxonomy Classification & Status

Every materialization and conversion boundary is classified in [05-materialization-map.csv](05-materialization-map.csv):

| Taxonomy Category | Count | Status | Strategic Treatment |
| --- | ---: | --- | --- |
| `VALIDATION_DIAGNOSTIC` | 19 | **Preserved & Documented** | Lazy evaluation with `.limit(10).collect()` only executed upon failure for error messaging. |
| `SCHEMA_INSPECTION` | 17 | **Preserved & Documented** | Zero-data cost schema checking (`.collect_schema()`) without materializing memory rows. |
| `STATEFUL_ALGORITHM_BOUNDARY` | 17 | **Preserved & Documented** | Invariant requirement for sequential FIFO lot matching, forward-fill FX, and date caching. |
| `PUBLICATION_BOUNDARY` | 7 | **Preserved & Documented** | Terminal stages materializing data for DuckDB lakehouse insertion or silver/gold parquet writes. |
| `THIRD_PARTY_BOUNDARY` | 6 | **Preserved & Documented** | Boundary requirements for SQLite parameter binding and external yfinance requests. |
| `SCALAR_EXTRACTION` | 3 | **Preserved & Documented** | Single scalar value retrieval (CPI index value, row counts for telemetry). |
| `PROCESS_BOUNDARY` | 1 | **Preserved & Documented** | Explicit runtime `gc.collect()` between execution phases. |
| `UNNECESSARY (ELIMINATED)` | 6 | **Eliminated in Phase 5** | Redundant `.collect().lazy()` conversions that added round-trip overhead removed. |

## Phase 5 Optimization Results

1. `src/personal_finance_etl/application/investments/aggregation_service.py`:
   - Eliminated redundant `.collect().lazy()` in group aggregation join (`lazy_df.join(master_cols, on="ISIN", how="left")` now remains lazy throughout the graph).
   - Documented `SCALAR_EXTRACTION` on unique closing dates collection.
   - Documented `PUBLICATION_BOUNDARY` on final analytics tables collection.
2. `src/personal_finance_etl/infrastructure/providers/files/sqlite.py`:
   - Eliminated five redundant `.collect().lazy()` calls on `zcategory_lazy`, `assetgroup_lazy`, `assets_lazy`, `currency_lazy`, and `inoutcome_lazy`. LazyFrames backed by in-memory tables returned directly without round-trip re-collection.
3. **Comprehensive Inline Documentation**:
   - All active `.collect()` calls across `market_sync.py`, `transformer.py`, `lifecycle.py`, `inflation.py`, `fx.py`, `benchmarks.py`, `dates.py`, `validation.py`, `market_state.py`, `transactions.py`, `gold.py`, `bronze.py`, and `silver.py` now contain explicit inline documentation comments declaring their architectural boundary category and rationale.
