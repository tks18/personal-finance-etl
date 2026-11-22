# PFETL v11 Implementation Invariants

Load this reference when a phase changes financial outputs, persistence, warehouse schemas, migration behavior, observability, recovery, CLI/GUI boundaries, or final certification.

## 1. Product invariant

PFETL is built primarily for Shan. Prefer low friction, explicit known-source behavior, maintainability, financial correctness, and analytical usefulness over hypothetical external-user extensibility.

## 2. Reliability invariants

- Keep the existing single-emitter observability architecture.
- Keep durable Control Plane run/artifact/provider/failure history.
- Keep Raw Store evidence/payload history.
- Preserve backup/restore and recovery semantics.
- Do not add a second logging/event path for CLI, PySide6, or diagnostics.

## 3. Configuration invariants

- `Settings` owns runtime locations and operational source configuration.
- `FinancialRules` owns financial methodology/classification.
- Known source format/parser and load semantics are code-owned unless the authoritative plan explicitly says otherwise.
- Hash policy may be configured at the known evidence/dataset level, but must preserve existing sync/rename identity semantics.
- Keep one statements root unless the authoritative plan is amended.

## 4. Reference-data invariants

Long-lived reference naming target:

- `column_master.csv`
- `mutual_fund_instrument_mapping.csv`
- `instrument_master.csv`
- `benchmark_master.csv`
- `currency_reference.csv`
- `financial_year_parameters.csv`
- `opening_balances.csv`

`benchmark_mapping.csv` is retired through a deliberate one-time migration to `instrument_master.csv`.

## 5. Warehouse invariants

### Bronze

- Source-oriented evidence.
- Semantic physical table names.
- Operational provenance may remain when useful for sync/debugging.

### Silver

- Preserve all current proven table boundaries/grains unless an explicit later decision changes them.
- Cleanup is primarily table rename, column rename, and consumer-proven dead-column removal.
- Do not delete ugly-looking source columns before migrating every consumer.

### Gold

- Preserve current analytical table topology initially.
- Do not reduce table count simply because measures overlap.
- Power BI convenience is a valid analytical-surface requirement.

## 6. Vocabulary invariants

Canonical target vocabulary favors:

- lowercase `snake_case`;
- `dim_`, `fact_`, `ref_` in Silver according to existing responsibility;
- descriptive analytical nouns in Gold;
- `instrument` for security/reference entity vocabulary;
- `fx` rather than mixed FX/Forex naming;
- `pnl` rather than slash-based P/L names;
- `financial_year` rather than `FY` in canonical warehouse names;
- `*_base`, `*_local`, and `fx_rate_to_base` only after current semantics are verified field by field.

Renaming never authorizes a unit or formula change.

## 7. Financial regression invariant

During non-finance migration phases, unchanged evidence + unchanged FinancialRules + unchanged market evidence must preserve existing financial truth.

Depending on touched scope, compare:

- household income/expense/transfer totals;
- account balances and net worth;
- investment quantities and market values;
- purchase/sale/lot IDs;
- realized events;
- reconciliation events;
- asset and FX P&L;
- XIRR/CAGR and benchmark metrics;
- tax-event IDs/amounts;
- wealth and FIRE outputs.

Any unexplained difference is a stop condition.

## 8. One-time migration invariant

PFETL may accept deliberate breaking migrations because the primary user controls both producer and consumer.

Preferred pattern:

1. verify current baseline green;
2. snapshot/backup;
3. preserve Raw Store and Control Plane;
4. migrate config/reference files where required;
5. rebuild DuckDB derived state;
6. update known consumers such as Power BI;
7. compare against the financial oracle;
8. remove obsolete compatibility code instead of carrying it indefinitely.

## 9. Presentation invariants

- One product binary: `pfetl`.
- CLI and GUI call shared application services.
- PySide6 GUI is an operations console.
- Future Analytics Studio is separate and initially read-only against PFETL analytical state.
- Power BI remains supported.
- No SQL workbench or financial-dashboard sprawl inside the operations GUI.

## 10. Program non-goals

Do not recreate:

- Config Studio;
- `pfetl-contracts`;
- separate PFETL organization requirements;
- SourceBinding / route / satisfiability architecture;
- user-defined transform DSLs;
- generic plugin systems;
- public multi-user migration guarantees;
- a runtime documentation portal;
- AI/ML financial truth.
