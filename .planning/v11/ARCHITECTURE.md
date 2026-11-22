# PFETL v11 Shan-First Target Architecture

## 1. Product boundary

PFETL owns deterministic financial truth and safe operation. Power BI and a future Analytics Studio consume that truth. Analytics Studio v1 is read-only and requires no contracts repository, API layer, or write path.

## 2. Configuration boundary

`Settings` owns runtime locations and simple evidence policy. `FinancialRules` remains the sole owner of financial methodology.

Target source vocabulary:

- `household_database`
- `statements_root`
- `column_master`
- `mutual_fund_instrument_mapping`
- `instrument_master`
- `benchmark_master`
- `currency_reference`
- `financial_year_parameters`
- `opening_balances`

File/provider type and full/incremental load semantics remain code-owned. Hash policy moves from file-type ownership to evidence-source ownership with only `NONE` and `CONTENT` behavior.

## 3. Reference data boundary

Long-lived manual reference files:

```text
column_master.csv
mutual_fund_instrument_mapping.csv
instrument_master.csv
benchmark_master.csv
currency_reference.csv
financial_year_parameters.csv
opening_balances.csv
```

`benchmark_mapping.csv` is retired after its instrument-classification responsibilities move into `instrument_master.csv`.

## 4. Warehouse boundary

Bronze remains source-oriented and may retain operational provenance, but physical table names become semantic and lowercase snake_case.

Silver preserves the current 24-table topology and current grains. It receives semantic table/column naming and only consumer-proven dead-column removal. No merge/split program exists.

Gold preserves the current 22-table topology initially. It receives semantic naming and proven cleanup. New analytics are added only where the existing analytical grain fits; create a new table only when a distinct grain genuinely requires one.

## 5. Canonical vocabulary

- `instrument` for the security/reference entity;
- `investment` for Shan's positions/transactions/analytical facts;
- `fx` rather than mixed `Forex`/`FX` naming;
- `pnl` rather than `P/L`;
- `financial_year` rather than `FY` in canonical warehouse names;
- `*_base`, `*_local`, and `fx_rate_to_base` where existing semantics prove the distinction.

Renames never imply unit or formula changes.

## 6. Presentation boundary

The CLI and GUI use application services. The PySide6 GUI is an operations console, not a financial dashboard. It does not directly mutate DuckDB/Control Plane or implement finance.

## 7. Documentation boundary

Retain `README.md` and useful Markdown under `/docs`. Remove the embedded docs application, MkDocs/ReadTheDocs portal, `pywebview`, bundled Mermaid runtime, svg-pan-zoom, and portal-specific frontend assets. Mermaid source blocks may remain for GitHub-native rendering. The Wiki is no longer a required governance surface.

## 8. Hard non-goals

- arbitrary source configuration;
- Config Studio;
- source binding / routing / satisfiability layers;
- separate `pfetl-contracts` repository;
- separate GitHub organization;
- plugin framework;
- multi-user/public compatibility architecture;
- SQL explorer inside the operations GUI;
- write-capable Analytics Studio;
- Core-owned rebalancing trade recommendations.
