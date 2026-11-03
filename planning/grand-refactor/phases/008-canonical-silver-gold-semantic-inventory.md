# Phase 008 - Canonical Silver/Gold Semantic Inventory

**Target release:** v9.6.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 007  
**Next:** Phase 009 - Source-Independent Financial Classification  
**Risk:** Low-Medium  
**Runtime behavior change:** None  
**Schema/persistence change:** None

## 1. Outcome

Turn the canonical-model archaeology into checked-in, machine-verifiable migration data before changing any Silver/Gold schema.

This phase produces three authoritative inventories:

1. precise row grain + identity semantics for every Silver contract;
2. a column-level disposition manifest covering all 533 current Silver columns;
3. a Gold dependency manifest mapping each of 22 Gold contracts to the Silver datasets/columns it consumes.

No canonical column is renamed today.

## 2. Why this phase exists

The next five phases modify source taxonomy, provenance and provider vocabulary inside the financial model.

Those migrations are unsafe if the repository cannot answer:
- what one row means;
- which columns are canonical finance vs source residue;
- which Gold producer consumes a column;
- whether an apparently ugly source field is actually needed for identity/audit.

The manifest is executable migration governance, not documentation prose.

## 3. Inherited state

Phases 001-007 changed foundational contracts only.

Current Silver/Gold physical schemas and financial outputs remain v9.5.3-compatible.

## 4. Current code anchors

- `infrastructure/warehouse/contracts.py::DATA_CONTRACT_REGISTRY`
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/schema/gold.py`
- all producers named by `DataContract.producer`
- Gold transformation/presentation modules
- current tests validating contract registry/schema parity

Current inventory:
- 24 Silver contracts;
- 533 Silver columns;
- 22 Gold contracts.

## 5. Target checked-in assets

Prefer structured Python/JSON/YAML only if it can be validated reliably in tests. Do not create a free-form Markdown ledger as the only authority.

### Silver contract semantics

For each Silver DatasetId:
- precise row grain;
- identity/key semantics;
- financial domain;
- current producer;
- future capability owner placeholder if not yet frozen.

### Silver column disposition

Every physical column receives exactly one classification:

```text
CANONICAL_FINANCIAL
CANONICAL_IDENTITY
PROVENANCE_REFERENCE
SOURCE_TAXONOMY
PROVIDER_METADATA
IMPLEMENTATION_RESIDUE
```

and one disposition:

```text
RETAIN
RENAME
MOVE_TO_PROVENANCE
MOVE_TO_PROVIDER_MAPPING
REMOVE_AFTER_CONSUMER_MIGRATION
REVIEW_REQUIRED
```

`REVIEW_REQUIRED` is allowed only if this phase records the exact code question and consumer preventing a decision. Phase completion should drive this count to zero wherever feasible.

### Gold dependency manifest

For each Gold DatasetId:
- producer;
- input Silver DatasetIds;
- input columns;
- output grain;
- current domain;
- external/presentation dependency if any.

## 6. Implementation sequence

### Step 1 - Parse/compare Silver DDL and registry

Add a test/helper that enumerates all Silver physical columns.

Assert manifest coverage equals DDL coverage exactly:
- no missing columns;
- no unknown manifest columns.

### Step 2 - Freeze precise Silver grains

Replace vague registry grain strings only where the new text is a semantic clarification and no runtime logic depends on the string.

Examples must express one-row meaning, not merely `"Category"` or `"Day"` where ambiguity remains.

If changing registry strings affects fingerprint tests, update them deliberately.

### Step 3 - Classify known source/provider residue

At minimum explicitly classify:
- `__file_name__`
- `__folder_path__`
- `__file_category__`
- `S_NO`
- `MODIFY_DATE`
- `DEVICE_ID`
- `USE_TIME`
- `ADDED_TIME`
- `INSERT_TYPE`
- `IS_SHOW`
- `yF_Ticker`
- `YAHOO_TICKER` where present.

Do not mark these REMOVE merely because names are ugly. Trace consumers.

### Step 4 - Classify remaining canonical columns

All 533 columns need a classification.

Use table/domain context and producer code. The point is to prevent future schema migration by intuition.

### Step 5 - Build Gold dependency manifest

Trace each Gold producer.

Tests should verify:
- all 22 Gold contracts covered;
- every declared Silver dependency exists;
- every declared input column exists in the current Silver DDL.

### Step 6 - Normalize Gold metadata where non-breaking

Stable DatasetId from Phase 001 is authoritative.

Correct obviously historical domain metadata only if no code uses the string for behavior. Otherwise record migration for later capability phase.

Do not rename physical Gold tables today.

## 7. Files expected in scope

Create:
- canonical-model migration manifest module/data;
- manifest validation tests.

Modify:
- `DATA_CONTRACT_REGISTRY` grain/domain metadata only where safe;
- registry tests.

Read extensively:
- Silver DDL;
- Gold DDL;
- household/investment/Tax/wealth producers.

## 8. Explicitly out of scope

Do not:
- rename/drop Silver columns;
- change financial formulas;
- change Gold outputs;
- add provenance keys;
- replace Yahoo symbols;
- modify Power BI/presentation compatibility.

## 9. Tests

Required:
- 24/24 Silver contracts represented;
- 533/533 Silver columns represented exactly once;
- zero unknown manifest columns;
- 22/22 Gold contracts represented;
- Gold dependencies reference real Silver contracts/columns;
- each Silver contract has precise grain and identity semantics;
- known source/provider residue has explicit disposition.

Add a test that future Silver DDL additions fail until the manifest is updated. This keeps the inventory authoritative during the refactor.

## 10. Real-data/performance

No runtime behavior should change.

No real-data run required beyond release regression.

No performance impact.

## 11. Observability/persistence/identity

No runtime effect.

The manifest may describe identity, but does not change it.


## 12. Explicit non-goals

Do not:
- rename, add or drop physical Silver/Gold columns;
- change financial formulas or producer behavior;
- implement provenance replacement;
- replace provider-specific symbols;
- introduce capability runtime behavior;
- use the manifest as a runtime dependency for financial calculations.

## 13. Completion checklist

- [x] Every Silver contract has precise row grain.
- [x] Every Silver contract has identity semantics.
- [x] All 534 Silver columns are classified.
- [x] All known source/provider residue has disposition.
- [x] All 22 Gold contracts have dependency entries.
- [x] Manifest coverage is enforced by tests.
- [x] No physical schema changed.
- [x] No financial output changed.

## 14. Commit

```text
chore(contracts): freeze canonical model migration inventory
```

## 15. Handoff to Phase 009

Phase 009 may use the manifest to identify every `__file_category__` occurrence that represents improper financial semantics.

The manifest remains authoritative until each row is closed by later migration phases.

## Phase completion record

Before committing, record:

```text
Phase: 008
Target release: v9.6.0
Files changed:
  src/personal_finance_etl/contracts/semantic_inventory.py
  src/personal_finance_etl/contracts/silver_column_dispositions.json
  src/personal_finance_etl/contracts/__init__.py
  src/personal_finance_etl/infrastructure/warehouse/contracts.py
  tests/contracts/test_semantic_inventory.py
  tests/infrastructure/test_warehouse_and_cp.py
Schema changed: NO (Metadata & contract inventory only; no DDL or DuckDB/SQLite schema migration)
Runtime behavior changed: NO (Additive contracts and manifests; zero runtime modification to analytical pipelines)
Financial formulas changed: NO
Focused tests: tests/contracts/test_semantic_inventory.py (8 passed)
Architecture tests: tests/architecture/test_boundaries.py (4 passed)
Real-data run: Validated end-to-end via existing live pipeline tests and full test suite (278 passed)
Performance check: Full Quality Gate audit completed in ~80s (0 regressions, fast gate < 1.1s)
Compatibility path still present: Complete v9.5.3-compatible analytical layer
Old path deleted: None (vague grain strings in DATA_CONTRACT_REGISTRY clarified to precise one-row grains)
Exit assertions green: YES
Commit: chore(contracts): freeze canonical model migration inventory
```

If any required exit assertion is false, this phase is not complete.
