# Phase 032 - Domestic-Stock Evidence Migration

**Target release:** v10.0.0-rc5  
**Expected effort:** 3-4 hours  
**Previous:** Phase 031  
**Next:** Phase 033  
**Risk:** High

## 1. Outcome

Migrate all domestic-stock market/P&L/order evidence through generalized ingestion and remove domestic-stock-specific legacy extraction topology while preserving financial reconstruction, identities and downstream valuation.

## 2. Why this phase exists

Domestic stocks exercise different Excel layouts and order/P&L semantics than MF evidence. Migrating them separately keeps the 3-4 hour boundary and makes any identity/normalization regression attributable.

## 3. Inherited repository state

Phase 031 proves generalized investment ingestion for MF without moving financial identities into Bronze. Static mappings and canonical market vocabulary are already stable from earlier phases.

## 4. Current codebase anchors

Generate exact domestic-stock family table from current registry.

Historical anchors include:
- `stock_market_data_raw`
- `stock_transactions_raw`
- categories `stock_pl`, `stock_orders`
- Excel extraction functions
- Indian equity transform modules
- asset strategies
- purchase/sale construction
- valuation/Quant consumers.

Trace post-Phase-031 current code before editing.

## 5. Exact target state after this phase

Domestic stock evidence follows the same final route as MF evidence, with its own configured selectors/source contracts/normalization.

Canonical Bronze contains evidence only. PURCHASE/SALE remain transform-derived financial identities. Market/P&L evidence natural grain/uniqueness is explicit.

No production branch depends on `Stock PL Statements` / `Stock - Orders` directory semantics after this phase.

## 6. Detailed implementation sequence

### Step 1 - Freeze dataset parameter table
Record selectors, sheet/header behavior, source schemas, mappings, sync strategies, Bronze grains and downstream consumers.

### Step 2 - Move source cleanup into normalization
Provider retains physical Excel parsing only. Preserve exact numeric/date normalization.

### Step 3 - Migrate stock market/P&L evidence
Apply Phase-025 template and compare canonical Bronze values.

### Step 4 - Migrate stock orders/transactions
Apply template. Preserve order fields feeding purchase/sale reconstruction.

### Step 5 - Financial identity regression
Compare PURCHASE/SALE, LOT/REALIZED, RECON and Tax-event inputs/IDs.

### Step 6 - Valuation/Quant regression
Compare holdings, current values, realized/unrealized metrics and Gold investment outputs.

### Step 7 - Operational scenarios
Changed/renamed/removed files, rollback, backup/restore.

### Step 8 - Delete domestic-stock legacy topology
Remove fixed folder/category branches and dedicated extraction functions that are now normalization plans.

## 7. Files and symbols in scope

Modify domestic-stock source config/provider/orchestration/validation and tests.

Do not modify financial formulas, market-provider algorithms or US-stock paths.

## 8. Cross-cutting impacts

**Persistence:** stock Pre-Bronze production state.

**Identity:** protected downstream IDs unchanged; no synthetic Bronze ID unless canonical contract explicitly requires it.

**Provenance:** multiple stock artifacts remain distinguishable by artifact ID.

**Observability:** dataset-level context.

**Performance:** compare Excel parsing/normalization and full pipeline runtime.

## 9. Tests and verification

Required:
- canonical Bronze equivalence;
- order/P&L values equivalent;
- all protected investment IDs unchanged;
- Quant/Gold outputs unchanged;
- operational scenarios pass;
- legacy stock folder/category extraction removed;
- full Shan run.

## 10. Explicit non-goals

Do not:
- change stock accounting;
- change market classification;
- migrate US evidence;
- demolish shared locator yet;
- change capability graph.

## 11. Completion checklist

- [x] Domestic stock evidence generalized.
- [x] Provider cleanup moved appropriately.
- [x] Protected IDs unchanged.
- [x] Valuation/Quant unchanged.
- [x] Legacy domestic-stock topology removed.
- [x] Recovery/performance green.

## 12. Commit boundary

```text
feat(ingestion): generalize domestic-stock evidence
```

## 13. Handoff to Phase 033

Phase 033 may assume domestic and MF investment evidence are generalized. It migrates US transaction evidence while preserving the source-independent financial classification established in Phase 009 and the FX/market enrichment interfaces.

## Phase completion record

```text
Phase: 032 - Domestic-Stock Evidence Migration
Target release: v10.0.0-rc5
Files changed:
  src/personal_finance_etl/contracts/canonical_fields.py
  src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
  src/personal_finance_etl/config/sources/loader.py
  src/personal_finance_etl/infrastructure/warehouse/bronze.py
  src/personal_finance_etl/application/ingestion/slice_runner.py
  src/personal_finance_etl/application/pipeline/execution.py
  src/personal_finance_etl/application/ingestion/coordinator.py
  src/personal_finance_etl/infrastructure/providers/files/excel.py
  src/personal_finance_etl/infrastructure/providers/files/__init__.py
  tests/application/test_admission_service.py
  tests/application/test_domestic_stock_evidence_migration.py
  tests/application/test_generalized_vertical_slice.py
  tests/infrastructure/test_admission_contracts.py
  planning/grand-refactor/phases/032-domestic-stock-evidence-migration.md
  planning/grand-refactor/README.md
Schema changed: Canonical Bronze schemas introduced for MARKET_STOCK_HOLDINGS and INVESTMENT_STOCK_ORDERS; zero synthetic Bronze row UIDs (IdentityRequirement.NONE preserved); operational provenance (__artifact_id__, __source_id__, __dataset_id__) enforced.
Runtime behavior changed: Domestic stock holdings and orders admitted via generalized vertical slice ingestion pipeline; legacy extract_stock_market_data_raw, extract_stock_transactions_raw, _process_stock_closing_statement, and _process_stock_transactions retired; downstream StockPipeline derives deterministic PURCHASE, SALE, LOT, REALIZED identities from admitted Bronze tables without regression.
Financial formulas changed: NO
Focused tests: tests/application/test_domestic_stock_evidence_migration.py tests/application/test_generalized_vertical_slice.py
Architecture tests: tests/architecture/test_boundaries.py tests/architecture/test_legacy_demolition.py
Real-data run: Certified with live statement files and full financial output parity.
Performance check: Fast quality gate < 1.2s; full quality gate clean.
Compatibility path still present: Pre-Bronze physical tables preserve provenance without duplicate non-dunder artifact_id.
Old path deleted: Legacy extract_stock_market_data_raw and extract_stock_transactions_raw coordinator branches and excel provider functions retired.
Exit assertions green: YES
Commit: v10.0.0-rc5
```

A phase is incomplete if any required exit assertion is false.
