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

- [ ] US transaction evidence generalized.
- [ ] Folder/category semantics removed from ingestion.
- [ ] Canonical classification preserved.
- [ ] Protected IDs unchanged.
- [ ] Enrichment requests unchanged.
- [ ] Recovery/performance green.

## 12. Commit boundary

```text
feat(ingestion): generalize us investment evidence
```

## 13. Handoff to Phase 034

Phase 034 may assume all user/file-backed investment evidence is generalized. Remaining Bronze migration work is provider-generated market history: currency FX, benchmark history and US market history.

## Phase completion record

```text
Phase:
Target release:
Files changed:
Schema changed:
Runtime behavior changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Real-data run:
Performance check:
Compatibility path still present:
Old path deleted:
Exit assertions green:
Commit:
```

A phase is incomplete if any required exit assertion is false.
