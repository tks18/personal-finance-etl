# Phase 004 - Complete v9.5.3 Topology as Declarative Configuration

**Target release:** v9.5.4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 003  
**Next:** Phase 005 - Change-Detection Policy Architecture  
**Risk:** Low  
**Runtime behavior change:** None  
**Schema/persistence change:** None

## 1. Outcome

Create a versioned test/example configuration representation of the complete v9.5.3 externally supplied source topology using the contracts from Phases 001-003, and add coverage tests proving every externally sourced Bronze DatasetId is representable.

This is a modeling proof, not runtime cutover.

## 2. Why this phase exists

Before adding policy, mapping or ingestion execution, the source model must prove it can describe the system it intends to replace. If a current source cannot be represented cleanly, the contracts are incomplete and should be fixed now while they are dormant.

## 3. Inherited state

Available:
- DatasetId registry;
- SourceId / ProviderType;
- SourceConfig;
- CSV/Excel/SQLite selectors;
- SourceDatasetConfig + compatibility validation.

Still authoritative at runtime:
- Settings source paths;
- `STATEMENTS_FOLDER` locator;
- `_inject_configuration_assets()`;
- `FILE_TYPE_MAP`;
- DataExtractor fixed methods;
- ExtractionResult.

## 4. Current topology to represent

### Settings-special sources
- household SQLite source (`SOURCE_DB_FOLDER` / discovered backup);
- column master CSV;
- MF ISIN CSV;
- benchmark mapping CSV;
- benchmark master CSV;
- macro parameters CSV;
- opening balance CSV;
- currency mapping CSV.

### Folder-discovered Excel categories
- `stock_pl` from `Stock PL Statements`;
- `mf_holdings` from `Mutual Funds - Holdings`;
- `stock_orders` from `Stock - Orders`;
- `mf_orders` from `Mutual Funds - Orders`;
- optional `us_stock_transactions` from `IND Money (US Stocks)/Transaction Reports`.

### Provider/internal generated Bronze streams
- currency history;
- benchmark history;
- US stock market history.

These provider-generated streams must be explicitly classified as not equivalent to user file sources. Do not force them into fake CSV/Excel SourceConfigs merely to make the coverage test green.

## 5. Exact Bronze universe to cover

Use `BRONZE_CONTRACT_REGISTRY` as the factual list. For each of its 20 entries classify:

```text
EXTERNAL_CONFIGURED_SOURCE
PROVIDER_GENERATED
TRANSITIONAL_CONFIGURATION_DATASET
```

`column_master` is transitional because its mapping semantics will move into typed source configuration later.

## 6. Implementation sequence

### Step 1 - Create topology fixture/example

Create a test fixture or example config object/file representing Shan's current topology using SourceConfig + SourceDatasetConfig.

Use placeholder/test-safe locations, not personal absolute paths.

### Step 2 - Map household SQLite tables

Represent the five current household datasets as separate SourceDatasetConfig bindings under one SQLite SourceId, each with its own SqliteSelector table name.

This proves one physical source can expose many canonical datasets.

### Step 3 - Map configured CSV dependencies

Represent MF ISIN, benchmark mapping/master, macro parameters, opening balances and currency mapping as configured CSV sources/datasets.

Represent `column_master` explicitly as transitional so later retirement is traceable.

### Step 4 - Map statement Excel sources

Represent current MF/stock/US statement evidence without encoding folder names as financial semantics. The fixture may preserve current physical locations, but DatasetId is the canonical meaning.

### Step 5 - Classify provider-generated datasets

Create an explicit set/metadata classification for currency history, benchmark history and US stock market data so the future SourcePlanner knows these are fulfilled by provider workflows, not required user file selectors.

Do not implement provider planning today.

### Step 6 - Add topology coverage test

Derive the current Bronze DatasetId set from the registry and assert every member is exactly one of:
- represented by SourceDatasetConfig;
- classified provider-generated;
- classified transitional with a documented retirement phase.

No unexplained Bronze dataset is allowed.

### Step 7 - Add uniqueness/coverage diagnostics

Failure should name missing/duplicated DatasetIds so future registry changes cannot silently bypass configuration modeling.

## 7. Files in scope

- test/example configuration fixture under the project's test/config conventions;
- source configuration validation helpers if coverage logic belongs there;
- focused tests.

### Explicitly do not modify
- Settings validation;
- locator;
- coordinator;
- providers;
- file sync;
- warehouse persistence;
- financial transforms.

## 8. Compatibility and release meaning

Phases 001-004 together form **v9.5.4**: an additive architecture-foundation patch/minor according to the project's actual SemVer policy, with zero production behavior change.

At release end, the new source model can describe the existing system but is not yet used to execute it.

## 9. Tests

Required:
- all 20 Bronze DatasetIds classified;
- no DatasetId represented twice unintentionally;
- five household datasets share one SQLite SourceId correctly;
- provider-generated datasets do not require user file SourceConfig;
- `column_master` is marked transitional;
- current US transaction source can be modeled as optional/enabled state without making all other statement sources optional;
- serialization round-trip for the complete topology fixture.

## 10. Real-data/performance

No real-data run required for behavioral proof because runtime is untouched. Full release gate may run the pipeline as a no-regression check.

## 11. Non-goals

Do not:
- remove Settings paths;
- load this configuration in production;
- add mappings;
- change required/optional capability semantics;
- generalize market providers;
- retire column_master yet.

## 12. Completion checklist

- [x] Every current Bronze dataset is classified.
- [x] Every externally supplied dataset is representable.
- [x] Provider-generated datasets are explicitly separated.
- [x] Transitional column_master is tracked.
- [x] No runtime code changed.
- [x] v9.5.4 foundation tests pass.
- [x] Full quality gate passes before tagging/releasing v9.5.4.

## 13. Commit

`test(config): model current source topology declaratively`

If model code must be adjusted because the fixture exposes a real gap, split into a small preceding `feat(config)` commit and keep the final topology proof commit focused.

## 14. Handoff to Phase 005

Phase 005 may assume the new configuration vocabulary can describe every current externally supplied Bronze dataset and explicitly classifies provider-generated/transitional datasets. Runtime still derives hashing/sync policy from v9.5.3 `FileHashPolicy`, `FILE_TYPE_MAP` and Bronze full-replace metadata.
