# v9.2.0 — Polars Execution Evidence

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

Primary hotspots: investment valuation/market state (10), investment common transforms (6, mostly schema inspection), market FX (5), SQLite provider (5), investment input adapter (4), common dates (4), investment aggregation (3), ISIN service (3).

Classify every boundary before changing it. The objective is longer useful lazy plans and fewer unnecessary Polars↔Python round-trips, not a prettier grep count.
