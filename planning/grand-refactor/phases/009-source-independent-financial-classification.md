# Phase 009 - Source-Independent Financial Classification

**Target release:** v9.6.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 008  
**Next:** Phase 010 - Canonical Provenance Model  
**Risk:** Medium-High  
**Runtime behavior change:** Internal classification path changes; financial results must remain identical  
**Schema/persistence change:** Prefer additive/rename-safe change only; no broad Silver cleanup yet

## 1. Outcome

Remove source category as a financial decision input.

At phase end no application/domain financial branch may decide that an instrument is US/Indian/MF/etc. because `__file_category__` says so.

Financial logic must use canonical financial classification such as instrument class, jurisdiction/country, market and/or currency as justified by the current model.

`__file_category__` may temporarily remain as provenance metadata for later Phase 010, but it has zero authority over finance.

## 2. Current code anchors

Known v9.5.3 references include:

- `application/pipeline/execution.py::_resolve_us_market_range`
- `application/ingestion/market_sync.py`
- `application/ingestion/asset_strategies.py`
- `domain/investments/transforms/us_equity.py`
- `domain/investments/transforms/indian_equity.py`
- `domain/investments/transforms/mutual_funds.py`
- `domain/investments/transforms/common.py`
- `domain/investments/valuation/market_state.py`

Examples:

```python
df.filter(pl.col("__file_category__") == "US Stocks")
```

and transforms that create/fill `"Indian"` / `"US Stocks"` source-category values.

## 3. Inherited state

Phase 008 provides a column disposition manifest and Gold dependency map.

Use that manifest to distinguish:
- provenance-only `__file_category__`;
- improper financial semantics.

Do not reclassify columns ad hoc outside the manifest without updating it.

## 4. Design decision for canonical classification

Before editing consumers, trace existing fields in:
- investment master;
- purchase/sale frames;
- market-state frames.

Prefer existing canonical finance fields if they already uniquely represent the needed decision:
- instrument class/type;
- country/jurisdiction;
- market;
- currency.

Only introduce a new canonical field if current canonical state cannot represent the distinction.

Do not create a replacement field called `SOURCE_CATEGORY` or copy `"US Stocks"` into a differently named column. That merely launders the coupling.

## 5. Target semantics

Examples:

```text
Need US market date range
  -> select purchases/instruments whose canonical market/jurisdiction requires US market data

Need FX valuation
  -> select positions whose valuation/base currency relationship requires FX

Need instrument routing
  -> route by canonical instrument type/class
```

The exact field(s) must be documented in the Phase 008 manifest and shared by all consumers.

## 6. Implementation sequence

### Step 1 - Freeze one canonical classification rule

Create or identify one reusable financial classification helper/contract.

Do not duplicate string comparisons across application and domain.

### Step 2 - Migrate `_resolve_us_market_range`

Replace `__file_category__` filter.

Add focused test using current US and domestic purchase data:
- selected date range identical before/after;
- domestic records excluded;
- empty-US case unchanged.

### Step 3 - Migrate `market_sync.py`

Use the same classification rule.

Verify:
- US market provider requests unchanged for Shan data;
- FX/benchmark request ranges unchanged.

### Step 4 - Migrate valuation market-state logic

Replace source-category filters in `domain/investments/valuation/market_state.py`.

This is financially sensitive. Add value-equivalence tests around:
- current market value;
- FX conversion;
- realized/unrealized components where affected.

### Step 5 - Migrate transform propagation

Stop creating/filling `__file_category__` for the purpose of later financial branching.

If it remains required as provenance until Phase 010, populate it only as provenance and make that ownership explicit.

### Step 6 - Migrate asset strategies

Any schema assumptions requiring `__file_category__` for finance must move to canonical classification.

### Step 7 - Add architecture guard

Fail tests if application/domain financial modules compare `__file_category__` for decisions.

A raw string search test may be acceptable during migration if scoped carefully; prefer AST/static rule if existing architecture-test framework supports it.

## 7. Files expected in scope

Modify the known references above plus focused tests.

Possibly modify Silver/transform schema additively if a genuinely missing canonical classification field is required.

Do not perform unrelated provider-symbol or provenance cleanup.

## 8. Persistence and schema

Preferred: reuse existing canonical fields, causing no DDL change.

If a new field is unavoidable:
- add it additively;
- populate deterministically;
- keep old provenance column until Phase 010;
- update contract/DDL tests;
- do not remove any old column in the same step unless zero consumers are proven.

## 9. Identity

No deterministic ID algorithm may change.

Classification fields used in existing PURCHASE/SALE identity inputs must not be changed casually. If an identity input currently includes `__file_category__`, inspect the exact namespace field set before migration and preserve byte-for-byte ID output through a compatibility canonical value.

Protected IDs:
- PURCHASE;
- SALE;
- LOT;
- REALIZED;
- RECON*;
- TAX.

## 10. Observability

Provider/entity labels may continue saying `"US"` or provider names.

No observability redesign.

If canonical classification is emitted as context, use stable finance vocabulary, not source folder category.

## 11. Tests

Required:
- US market range equivalence;
- market provider request equivalence;
- valuation equivalence;
- purchase/sale deterministic IDs unchanged;
- lot/realized/reconciliation/Tax IDs unchanged;
- no financial decision compares `__file_category__`;
- full Shan pipeline financial outputs unchanged.

## 12. Performance

Classification should be columnar/vectorized.

No new row-wise Python classification over large frames.

Full-run runtime should remain within noise.

## 13. Delete / retain

Delete now:
- financial decision branches on `__file_category__`.

Retain temporarily:
- `__file_category__` only where needed for provenance/compatibility;
- file category in Control Plane;
- source category in legacy ingestion topology.

Phase 010 owns provenance replacement.

## 14. Non-goals

Do not:
- remove `__file_name__`/`__folder_path__`;
- redesign market providers;
- rename Yahoo fields;
- alter financial taxonomy beyond what is required to remove source coupling;
- change capability execution.

## 15. Completion checklist

- [ ] Canonical financial classification is explicit.
- [ ] Pipeline US market range no longer uses source category.
- [ ] Market sync no longer uses source category for finance.
- [ ] Valuation no longer uses source category for finance.
- [ ] Domain transforms no longer create source category as financial truth.
- [ ] Protected IDs unchanged.
- [ ] Full Shan outputs unchanged.
- [ ] Architecture guard prevents regression.

## 16. Commit

```text
refactor(investments): remove source-category financial logic
```

## 17. Handoff to Phase 010

Phase 010 may assume `__file_category__` is provenance-only wherever it still exists.

It must preserve Control Plane source/artifact truth while replacing Silver/path-based lineage with explicit provenance references.

## Phase completion record

Before committing, record:

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

If any required exit assertion is false, this phase is not complete.
