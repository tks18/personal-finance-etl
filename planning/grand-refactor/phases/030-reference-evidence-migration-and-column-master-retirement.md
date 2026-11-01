# Phase 030 - Reference Evidence Migration and Column-Master Retirement

**Target release:** v10.0.0-rc3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 029  
**Next:** Phase 031  
**Risk:** High

## 1. Outcome

Migrate the remaining static/reference/configuration-backed evidence assigned to this family through generalized ingestion, then retire `column_master.csv` as a production data-plane dataset after proving all of its mapping semantics are configuration-authoritative.

Target family includes the current MF ISIN mapping, benchmark mapping/master, macro parameters, currency mapping and other static/reference inputs identified by the migration ledger, excluding market-provider history and investment transaction/market evidence scheduled later.

## 2. Why this phase exists

After household migration, the next low-volatility family is static/reference evidence. `column_master` is architecturally special: it was historically ingested as data but its meaning has already moved into typed configuration in Phases 018-019. Keeping it as Bronze evidence after that cutover would preserve two mapping authorities.

## 3. Inherited repository state

Phase 029 guarantees household evidence is fully generalized. Phase 019 guarantees every current `column_master` mapping is represented and parity-guarded in SourceConfiguration. Phase 020 fingerprints that configuration.

At phase start, use the Bronze migration ledger to enumerate exact remaining static/reference datasets. Do not include provider-generated history (`currency_fx_raw`, benchmark history, US market history) or investment evidence assigned to later phases.

## 4. Current codebase anchors

Historical examples:
- `stg_mf_isin_mapping`
- `stg_benchmark_mapping`
- `raw_benchmark_master`
- `raw_macro_parameters`
- `currency_mapping_raw`
- `column_master`
- any remaining static configured CSV/reference source from the 20-contract ledger.

Each non-column-master dataset receives SourceId, configured file selector, source schema, normalization, identity/grain, Pre-Bronze and canonical Bronze.

`column_master` receives a different disposition: REMOVE as data-plane evidence after parity proof.

## 5. Exact target state after this phase

For every in-scope static/reference dataset, the Phase-025 vertical route is authoritative.

For `column_master`:
```text
BEFORE
CSV file -> Raw/legacy extraction -> column_master frame -> get_column_mapping -> transforms

AFTER
SourceConfiguration.mapping/normalization -> compiled NormalizationPlan -> admission/transforms
```

There is exactly one mapping authority after the phase: SourceConfiguration.

## 6. Detailed implementation sequence

### Step 1 - Generate exact family table from registry/ledger
Classify each current Bronze stream as `MIGRATE_REFERENCE` or `NOT_THIS_PHASE`. Assert no stream is silently omitted.

### Step 2 - Migrate each static/reference dataset
Use Phase-025 template. These are generally full-replace/config-scale; preserve exact downstream values.

### Step 3 - Validate reference-specific grains
Examples: ISIN mapping uniqueness, benchmark identity, currency mapping uniqueness, macro parameter key/value grain. Do not synthesize row IDs where natural canonical grain suffices.

### Step 4 - Prove column-master parity globally
Compare every current column-master row/semantic mapping against typed SourceConfiguration. No production mapping consumer may read column-master without an equivalent config entry.

### Step 5 - Switch remaining mapping consumers
All household/reference transforms use compiled mapping plans/config, not `get_column_mapping()`/`mappings[...]` sourced from the CSV.

### Step 6 - Remove column-master source as evidence
Delete its special Settings path if unused, manual injection category, CSV extractor, Bronze contract/DatasetId if used only for the data-plane mapping file, and any compatibility persistence expectation.

### Step 7 - Delete `get_column_mapping` legacy mechanism
Only after zero consumers.

### Step 8 - Architecture guard
Mapping semantics must originate from SourceConfiguration; no external mapping CSV may become an undeclared second authority.

### Step 9 - Full reference/financial regression
Benchmark/currency/investment-master downstream values unchanged.

## 7. Files and symbols in scope

Modify:
- static/reference SourceConfigs and contracts;
- CSV provider/extractor routes;
- mapping consumers;
- Settings/manual injection;
- Bronze registry entries;
- tests.

Delete column-master-specific runtime artifacts after proof.

Read but do not migrate:
- provider-generated market history;
- MF/stock/US transaction and market evidence.

## 8. Cross-cutting impacts

**Persistence:** reference datasets gain Pre-Bronze; column-master Bronze/data-plane contract is retired.

**Configuration:** SourceConfiguration becomes sole mapping authority.

**Identity:** natural reference grains preferred; no unnecessary synthetic IDs.

**Provenance:** static files remain traceable through artifact/source/dataset IDs.

**Observability:** mapping config fingerprint already identifies interpretation; column-master file events disappear because it is no longer evidence.

**Performance:** config mapping avoids reading/parsing column_master every run; no regression expected.

## 9. Tests and verification

Required:
- exact family ledger coverage;
- each migrated reference dataset source/Bronze validation;
- downstream reference values identical;
- all column-master semantics represented in config;
- zero production reads of `COLUMN_MASTER_PATH`;
- zero `get_column_mapping` consumers;
- column-master injection/extractor/contract removed;
- mapping architecture guard;
- full Shan financial/ID regression;
- config fingerprint changes only as intentionally expected.

## 10. Explicit non-goals

Do not:
- remove generic CSV provider;
- migrate market history;
- migrate MF/stock transaction evidence;
- change benchmark/FX methodology;
- add arbitrary mapping language.

## 11. Completion checklist

- [ ] All in-scope static/reference datasets generalized.
- [ ] Natural grain/uniqueness enforced.
- [ ] SourceConfiguration is sole mapping authority.
- [ ] `column_master` production path removed.
- [ ] `get_column_mapping` legacy path removed.
- [ ] Settings/manual injection cleaned.
- [ ] Reference downstream outputs unchanged.
- [ ] Full Shan run green.

## 12. Commit boundary

```text
refactor(config): retire column-master data path
```

## 13. Handoff to Phase 031

Phase 031 may assume:
- no fixed dataset transport exists;
- household evidence is fully generalized;
- static/reference evidence is generalized;
- mapping configuration is sole authority;
- Pre-Bronze/Pandera/recovery patterns are proven repeatedly.

Phase 031 begins the higher-risk investment evidence migrations, starting with mutual funds while preserving later-layer financial identity semantics.

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
