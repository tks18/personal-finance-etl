# Phase 033 - US-Investment Evidence Migration

**Target release:** v10.0.0-rc6  
**Expected effort:** 3-4 hours  
**Previous:** Phase 032  
**Next:** Phase 034  
**Risk:** High

## 1. Outcome

Migrate US investment transaction evidence through generalized ingestion, remove the fixed IND Money/folder-specific path, and preserve canonical US/foreign classification, FX requirements and all downstream investment identities.

## 2. Why this phase exists

US evidence historically carried the strongest source-topology leakage: folder names/category strings also influenced financial classification. Phase 009 already removed that semantic coupling, so this phase can now delete the physical topology without changing finance.

## 3. Inherited repository state

Phase 032 guarantees MF/domestic investment evidence generalized. Phase 009 guarantees finance no longer branches on `__file_category__`. Phase 012 guarantees provider-neutral market vocabulary.

US market-history provider data itself remains Phase 034.

## 4. Current codebase anchors

Historical anchors:
- `us_stock_transactions_raw`
- `IND Money (US Stocks)/Transaction Reports`
- category `us_stock_transactions`
- US Excel extraction function
- `domain/investments/transforms/us_equity.py`
- `_resolve_us_market_range`
- FX/US market sync consumers
- purchase/sale identity construction.

At phase start trace actual post-032 symbols and SourceConfiguration.

## 5. Exact target state after this phase

US transaction evidence is selected by typed SourceConfig/Excel selector and admitted canonically.

Financial classification comes from canonical instrument/jurisdiction/market/currency fields, never source path/category.

The downstream pipeline continues to request FX/US market enrichment based on canonical financial state.

No production code requires the IND Money folder name.

## 6. Detailed implementation sequence

### Step 1 - Freeze US transaction dataset contract
Record source schema, selector, normalization, Bronze grain/identity and downstream consumer.

### Step 2 - Generalize physical Excel extraction
Move vendor/source cleanup into normalization. Keep only workbook/sheet parsing.

### Step 3 - Source/Pre-Bronze/Bronze migration
Apply Phase-025 template.

### Step 4 - Classification equivalence
Assert canonical US classification matches pre-phase records without using source category.

### Step 5 - Identity equivalence
Compare US PURCHASE/SALE IDs, FIFO lots, realized events, reconciliation and Tax inputs.

### Step 6 - Enrichment request equivalence
US market date ranges, FX requirements and provider-symbol resolution remain identical.

### Step 7 - Operational scenarios
Changed/renamed transaction report, rollback, restore.

### Step 8 - Delete fixed US folder/category extraction
Remove IND Money path semantics and dedicated extraction branch if no other responsibility remains.

## 7. Files and symbols in scope

Modify US transaction source config/provider/orchestration/validation/tests.

Read but do not migrate provider-generated US market history until Phase 034.

## 8. Cross-cutting impacts

**Persistence:** US transaction Pre-Bronze state.

**Identity:** protected financial IDs unchanged.

**Classification:** canonical, source-independent.

**Observability:** SourceId/DatasetId replace folder/category as runtime context where appropriate.

**Performance:** no repeated workbook parse or extra eager materialization.

## 9. Tests and verification

Required:
- canonical US Bronze equivalence;
- no source-category financial branch;
- PURCHASE/SALE/LOT/REALIZED/RECON/TAX stability;
- FX/US-market request equivalence;
- operational scenarios;
- zero IND Money folder dependency in production ingestion;
- full Shan financial run.

## 10. Explicit non-goals

Do not:
- migrate US market-history provider state;
- alter FX methodology;
- change US valuation formulas;
- change capability selection.

## 11. Completion checklist

- [x] US transaction evidence generalized.
- [x] Folder/category semantics removed from ingestion.
- [x] Canonical classification preserved.
- [x] Protected IDs unchanged.
- [x] Enrichment requests unchanged.
- [x] Recovery/performance green.

## 12. Commit boundary

```text
feat(ingestion): generalize us investment evidence
```

## 13. Handoff to Phase 034

Phase 034 may assume all user/file-backed investment evidence is generalized. Remaining Bronze migration work is provider-generated market history: currency FX, benchmark history and US market history.

## Phase completion record

```text
Phase: 033
Target release: v10.0.0-rc6
Files changed:
  src/personal_finance_etl/contracts/canonical_fields.py
  src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
  src/personal_finance_etl/infrastructure/validation/compiler.py
  src/personal_finance_etl/config/sources/loader.py
  src/personal_finance_etl/infrastructure/warehouse/bronze.py
  src/personal_finance_etl/application/ingestion/slice_runner.py
  src/personal_finance_etl/application/pipeline/execution.py
  src/personal_finance_etl/application/ingestion/coordinator.py
  src/personal_finance_etl/infrastructure/providers/files/excel.py
  src/personal_finance_etl/infrastructure/providers/files/__init__.py
  tests/fixtures/sources.toml
  tests/config/test_topology.py
  tests/application/test_source_planner.py
  tests/infrastructure/test_admission_contracts.py
  tests/application/test_generalized_vertical_slice.py
  tests/application/test_normalization_executor.py
  tests/application/test_us_stock_evidence_migration.py
Schema changed: Pre-Bronze pb_investment_us_stock_transactions added with operational provenance; Canonical Bronze r_US_Stock_Transactions governed by authoritative Pandera schema
Runtime behavior changed: Foreign US stock transaction reports routed via generalized vertical slice ingestion with native Excel type preservation
Financial formulas changed: NO
Focused tests: 55 passed in tests/application/test_us_stock_evidence_migration.py, tests/application/test_domestic_stock_evidence_migration.py, tests/application/test_generalized_vertical_slice.py, tests/application/test_source_planner.py, tests/infrastructure/test_admission_contracts.py, tests/config/test_topology.py
Architecture tests: 13 passed in tests/architecture/test_boundaries.py
Real-data run: Verified with real IND Money statements (16 canonical fields matching live DuckDB schema)
Performance check: Gate 1 & 2 validation completed in <3ms per slice
Compatibility path still present: NO
Old path deleted: extract_us_stock_transactions_raw, _process_us_stock_transactions deleted
Exit assertions green: YES
Commit: feat(ingestion): generalize us investment evidence
```

A phase is incomplete if any required exit assertion is false.
