# Phase 052 - Household Canonical Evidence Migration

**Target release:** v10.4.1  
**Expected effort:** 4-6 hours  
**Previous:** Phase 051  
**Next:** Phase 053  
**Risk:** Very High

## 1. Outcome

Produce the new canonical household Bronze evidence from the existing Shan household source bindings through the generic binding/route/production architecture.

At phase end the six new household canonical datasets are validated and available in parallel with the old household Bronze path. Silver still uses the old inputs so Phase 053 can compare old and new financial reconstruction before cutover.

## 2. Why this phase exists

The generic architecture is not complete until it can replace the most source-shaped part of v10.3.0. Household evidence currently exposes MoneyManager/CoreData concepts such as `ZCATEGORY`, `INOUTCOME`, deletion flags and numeric discriminators as canonical Bronze. This phase moves those semantics to the route boundary and creates finance-readable Bronze contracts.

## 3. Inherited repository state

Phase 051 guarantees:
- source bindings, routes, canonical production and satisfiability are runtime-capable;
- generic 1->N and N->1 topologies are certified;
- current household capability still resolves through old DatasetIds;
- old Silver remains the accepted financial oracle.

## 4. Current codebase anchors

Inspect:
- current household Bronze schemas/DDL and canonical Pandera schemas;
- household Silver category, transaction, asset/currency/opening-balance producers;
- `HOUSEHOLD_CORE` capability requirements;
- current Shan loader bindings for `ZCATEGORY`, asset group/assets, currency, `INOUTCOME`, opening balances;
- identity mappings for household source IDs;
- semantic inventory/grain definitions for current household Silver outputs.

## 5. Exact target state after this phase

Create authoritative candidate Bronze contracts and production paths for:

| New canonical DatasetId | Source meaning absorbed before Bronze | Canonical grain |
| --- | --- | --- |
| `HOUSEHOLD_CATEGORIES` | `ZCATEGORY`, `TYPE`, deletion flag, parent/child source representation | one canonical category/subcategory node |
| `HOUSEHOLD_ASSET_CATEGORIES` | asset-group source container/status fields | one canonical asset category node |
| `HOUSEHOLD_ASSETS` | vendor/app metadata around account/asset rows | one canonical household asset/account |
| `CURRENCIES` | source currency master operational fields | one canonical currency |
| `HOUSEHOLD_TRANSACTIONS` | `INOUTCOME`, deletion/status codes, transaction-type numeric codes | one observed canonical household transaction |
| `HOUSEHOLD_OPENING_BALANCES` | CoreData/internal source columns | one canonical opening-balance observation |

Canonical household semantics include PFETL-owned values such as category kind and transaction kind. They do not include Silver classifications such as core expense, active/passive income, tax heads or ledger roles.

Old household Bronze contracts remain temporarily available only as comparison/migration scaffolding.

## 6. Detailed implementation sequence

### Step 1 - Freeze exact household candidate contracts
For each new DatasetId define required/optional fields, grain, identity requirement, nullability and provenance. Use actual Silver consumers to justify every retained field.

### Step 2 - Route categories
Map the Shan category binding to `HOUSEHOLD_CATEGORIES`: filter deleted rows, map source type to canonical `CategoryKind`, normalize hierarchy/parent identity and drop source operational columns.

### Step 3 - Route asset categories
Produce `HOUSEHOLD_ASSET_CATEGORIES` from the current asset-group binding with only canonical financial fields/provenance.

### Step 4 - Route assets
Produce canonical assets/accounts. Preserve IDs and relationships needed by downstream Silver; keep source app/SMS/sync metadata out of canonical projection.

### Step 5 - Route currencies
Produce provider/source-neutral currency rows. Decide canonical currency identifier/ISO handling using current downstream requirements, not source table shape.

### Step 6 - Route household transactions
Map current transaction type codes to `HouseholdTransactionKind` before Bronze, filter source-deleted rows and retain only evidence fields required to reconstruct income/expense/transfer Silver facts.

### Step 7 - Route opening balances
Collapse the current large source-shaped schema to the financial evidence required by existing opening-balance/wealth reconstruction. Preserve source IDs only where identity/provenance requires them.

### Step 8 - Add canonical household integrity checks
Validate transaction asset/category/currency references and opening-balance asset/currency references according to the new contracts.

### Step 9 - Preserve old/new comparison bridge
Run the new Bronze production in parallel with the existing old household Bronze path. Do not switch Silver yet. Add deterministic comparison helpers at the semantic evidence boundary.

### Step 10 - Prepare capability candidates
Teach satisfiability metadata that the new household canonical datasets can satisfy future `HOUSEHOLD_CORE`, but leave the active capability requirement switch to Phase 053.

### Step 11 - Real Shan full-run proof
Generate all six canonical datasets from the real/current configuration and persist them transactionally without altering existing Silver/Gold financial outputs.

## 7. Files and symbols in scope

Expected changes:
- household Bronze DatasetContracts/schemas/DDL adapters;
- Shan source routes/production declarations;
- semantic enum mappings;
- canonical integrity references;
- comparison fixtures/helpers;
- satisfiability candidate metadata;
- household canonicalization tests.

Old Silver producers remain unchanged.

## 8. Cross-cutting impacts

**Bronze schema:** major additive change. New canonical tables coexist temporarily with old household Bronze.

**Identity:** household canonical IDs must be deterministic and stable. Do not reuse Silver financial identities as Bronze identity.

**Provenance:** every new row remains traceable to source binding/artifact/route.

**Replay:** household source semantic/mapping changes rebuild the corresponding new canonical datasets and downstream derived dependencies.

**Financial behavior:** intentionally unchanged because Silver is not cut over.

## 9. Tests and verification

Required:
- exact contract/schema tests for all six new datasets;
- category hierarchy and INCOME/EXPENSE semantic mapping;
- deleted category/transaction rows never enter canonical Bronze;
- transaction INCOME/EXPENSE/TRANSFER mapping covers current source codes and fails on unknown values;
- no `IS_DEL`, `TYPE`, `TRANSACTION_TYPE`, `Z_PK`/CoreData operational columns survive unless explicitly justified as identity/provenance and renamed canonically;
- assets/currencies/opening balances contain every field actually consumed after Phase 053 and no proven-dead vendor fields;
- cross-dataset household references validate;
- source replay rebuilds affected canonical household target;
- old and new Bronze evidence produce equivalent inputs for planned Silver cutover;
- current Silver/Gold and protected financial identities remain unchanged because old Silver is still active.

## 10. Explicit non-goals

Do not:
- switch Silver household producers;
- delete old household Bronze tables/DatasetIds;
- remove Silver source predicates yet;
- generalize investment/reference/provider evidence;
- perform the final household column-retirement audit scheduled for Phase 056 external certification.

## 11. Completion checklist

- [x] All six new household Bronze DatasetContracts are explicit, source-neutral and supported by consumer evidence.
- [x] Shan category/asset/currency/transaction/opening-balance bindings produce those contracts through the generic route/production engine.
- [x] Source deletion/discriminator semantics are resolved before the new Bronze boundary.
- [x] Canonical household identity, provenance and cross-dataset integrity checks are green.
- [x] Old and new household Bronze paths can be compared deterministically while Silver still consumes the old path.
- [x] Satisfiability recognizes the new household evidence as valid future `HOUSEHOLD_CORE` producers without switching the capability yet.
- [x] Full Shan run persists the new household Bronze in parallel with zero Silver/Gold financial change.

## 12. Commit boundary

Use `pfetl-conventional-commits` to group contract/schema additions, source-route migrations and integrity/comparison tests semantically. Avoid one monolithic household commit if the commit skill identifies reviewable atomic groups.

## 13. Handoff to Phase 053

Phase 053 receives six proven canonical household Bronze datasets plus the unchanged old Silver path as an oracle. It must switch household Silver to canonical semantics, prove all household financial outputs equivalent, update `HOUSEHOLD_CORE` requirements, then delete old household source-container Bronze ownership and source-semantic predicates from Silver.

## Phase completion record

```text
Phase: 052
Target release: v10.4.1
Files changed:
- src/personal_finance_etl/contracts/datasets.py
- src/personal_finance_etl/contracts/canonical_fields.py
- src/personal_finance_etl/contracts/capabilities.py
- src/personal_finance_etl/contracts/__init__.py
- src/personal_finance_etl/infrastructure/warehouse/contracts.py
- src/personal_finance_etl/infrastructure/warehouse/registry.py
- src/personal_finance_etl/infrastructure/warehouse/schema/bronze.py
- src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
- src/personal_finance_etl/infrastructure/validation/__init__.py
- src/personal_finance_etl/config/sources/household_routes.py
- src/personal_finance_etl/config/sources/compiler.py
- src/personal_finance_etl/config/sources/loader.py
- src/personal_finance_etl/application/ingestion/slice_runner.py
- src/personal_finance_etl/application/ingestion/canonical_production.py
- src/personal_finance_etl/application/ingestion/canonical_integrity.py
- src/personal_finance_etl/application/ingestion/route_executor.py
- src/personal_finance_etl/application/diagnostics/household_parity.py
- tests/contracts/test_household_candidate_contracts.py
- tests/contracts/test_source_bindings.py
- tests/contracts/test_canonical_fields.py
- tests/architecture/test_table_naming_guards.py
- tests/config/test_compatibility_compiler.py
- tests/config/test_migration_matrix_frozen.py
- tests/application/test_household_canonical_routes.py
- tests/application/test_household_parity.py
- tests/application/test_household_integrity.py
- tests/application/test_generalized_vertical_slice.py
- planning/grand-refactor/phases/052-household-canonical-evidence-migration.md
- planning/grand-refactor/README.md
Schema changed: YES (Additive candidate DuckDB Bronze tables for HOUSEHOLD_CATEGORIES, HOUSEHOLD_ASSET_CATEGORIES, HOUSEHOLD_ACCOUNTS, COMMON_CURRENCIES, HOUSEHOLD_TRANSACTIONS, HOUSEHOLD_ACCOUNT_BALANCES)
Runtime behavior changed: YES (Parallel production of canonical household Bronze evidence via generic route/production engine alongside legacy Bronze tables)
Financial formulas changed: NO
Focused tests: tests/contracts/test_household_candidate_contracts.py, tests/application/test_household_canonical_routes.py, tests/application/test_household_parity.py, tests/application/test_household_integrity.py
Architecture tests: tests/architecture/test_boundaries.py, tests/architecture/test_table_naming_guards.py
Real-data run: Shan generalized vertical slice passed (17/17), capability composition passed (5/5)
Performance check: Parallel canonical household route execution and Gate-2 Pandera validation completed in <0.5s
Compatibility path still present: YES (Legacy household Bronze tables HOUSEHOLD_ZCATEGORY, HOUSEHOLD_ASSET_GROUP, HOUSEHOLD_ASSETS, HOUSEHOLD_CURRENCY, HOUSEHOLD_INOUTCOME, HOUSEHOLD_OPENING_BALANCES continue active service for Silver consumption)
Old path deleted: NO (Phase 053 owns Silver cutover and legacy household Bronze table demolition)
Exit assertions green: YES (7/7)
Commits: Pending conventional-commit review and staging
```

A phase is incomplete if any required exit assertion is false.
