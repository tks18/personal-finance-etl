# Phase 046 - External Household Topology Certification

**Target release:** v10.3.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 045  
**Next:** Phase 047  
**Risk:** High

## 1. Outcome

Certify that PFETL's generalized household ingestion works for three genuinely different external source topologies, not merely Shan's topology expressed through configuration:

1. Excel household evidence without stable source UIDs;
2. CSV household evidence without stable source UIDs;
3. SQLite household evidence with stable IDs but a schema/table layout different from Shan's source.

Slim down and prune canonical Bronze and Silver household schemas:
- Prune unnecessary vendor columns (e.g. 53 raw MoneyManager columns in `household_opening_balances` and `household_transactions`) down to only the fields that are financially meaningful and required for downstream analytics (`UID`, `Date`/`TRANSACTION_DATE`, `AMOUNT`, `ASSET_SUBCATEGORY_ID`, `CURRENCY_ID`, `DESCRIPTION`, `artifact_id`).
- Pre-Bronze safely preserves all raw source-shaped columns, while Bronze and Silver expose clean, minimal financial contracts that any external user can easily map.

Each fixture must configure PFETL without source-code changes and reach canonical household Silver/Gold outputs or the maximum household-only outputs allowed by the active capability plan.

## 2. Why this phase exists

The architecture has already proven individual no-UID and household-only cases. External certification now tests the product claim at topology level: can a new user describe materially different evidence and still enter the same canonical financial model?

Furthermore, canonical Bronze schemas historically retained dozens of vendor-specific columns (such as MoneyManager's 53 internal columns in opening balances). Expecting external users to map 50+ unused vendor fields is unusable; Bronze schemas must be slimmed down to the core financial attributes needed for downstream reconciliation, budgeting, and net worth calculations. This phase should expose any hidden assumptions that survived the migration.

## 3. Inherited repository state

Phase 045 guarantees:
- PFETL-native configuration diagnostics and dry-run admission;
- generalized ingestion is authoritative;
- household-only capability works;
- trusted and derived Bronze identity strategies exist;
- mapping/normalization/Pandera/recovery are production paths;
- plan-aware warehouse is operational.

No companion configuration application is in scope.

## 4. Current codebase anchors

Use application/CLI interfaces from Phase 045 as the external user's entry point.

Build fixtures under the existing test/fixture conventions. They must not import Shan production data.

For each topology identify:
- SourceConfig(s);
- DatasetIds supplied;
- physical selectors;
- source schemas;
- mappings/normalization;
- identity strategies;
- household capability selection;
- expected canonical Bronze grains;
- expected Silver/Gold outputs.

Use current canonical contracts, never fixture-specific schema branches.

## 5. Exact target state after this phase

Three independent configurations satisfy the same canonical household contracts.

### Excel fixture
- realistic vendor-style column names;
- multiple sheets if useful to exercise selector behavior;
- no stable UID;
- deterministic Bronze identity from configured canonical fields.

### CSV fixture
- different source column names/order/date format from Excel;
- no stable UID;
- same canonical identity/grain outcome.

### SQLite fixture
- different table names from Shan;
- configured selectors;
- stable source IDs preserved;
- no hard-coded `zcategory`/legacy table-name dependency;
- Single-Source Divergence: certifies that a single SQLite container cleanly fans out into multiple distinct Bronze datasets (`household_transactions`, `household_categories`, `household_assets`) via typed table selectors.

### Multi-Source Convergence & Row-Level Divergence Certification
1. **Multi-Source Convergence (Unioning):**
   - Certifies that when an external user provides separate evidence files or sheets (e.g. an Excel workbook with sheet `Income_Categories` and sheet `Expense_Categories`), PFETL normalizes and unions them into a single canonical `bronze.household_categories` evidence dataset using declarative constant injection (`transforms: { TYPE = 0 }` vs `transforms: { TYPE = 1 }`).
2. **Single-Source Divergence (Semantic Fan-Out):**
   - Certifies that when an external user provides a combined evidence table (such as Shan's monolithic category table or a unified cashflow log), Bronze ingests the complete evidence stream intact, and Silver's transformation contracts deterministically fan out the records into the 4 distinct Silver dimensions (`silver.wealth_income_category`, `silver.wealth_income_subcategory`, `silver.wealth_expense_category`, `silver.wealth_expense_subcategory`) without loss of financial meaning.
3. **Inline Category Synthesis:**
   - Certifies that when an external user provides a transaction log without an accompanying category master (e.g. a flat CSV with `Category` and `Subcategory` text columns), `SourcePlanner` dynamically synthesizes canonical category dimensions on the fly.

All run:
```text
validate-config
check-sources
dry-run-admission
full household run
incremental/no-change rerun
```

No source code changes between fixtures.

## 6. Detailed implementation sequence

### Step 1 - Define fixture contracts and Generic External Fixture Repository
Establish a permanent Generic External Fixture repository at `tests/fixtures/external/household/` containing completely vendor-agnostic files with novel schemas:
- `generic_expenses.csv`: column names `Txn_Date`, `Category_Label`, `Spent_Amount`, `Payment_Mode`, `Notes` (dates formatted as `DD/MM/YYYY`);
- `generic_accounts.xlsx`: multi-sheet workbook with sheets `Bank_Accounts` and `Category_Catalog` with custom header offsets and column names;
- `generic_household.sqlite`: custom SQLite database with tables `custom_transactions`, `custom_categories`, `custom_accounts` and integer primary keys;
- Minimal, Capability-Scoped Financial Rules Fixtures:
  - `rules_household_minimal.toml`: concise 25-line financial rules declaring strictly household categorization (`[income]`, `[expense]`, `[budget]`) and zero tax or FIRE parameters. Proves external household users are never burdened with unneeded domain rules.
  - `rules_household_wealth.toml`: pairs household categories with cashflow pools and illiquid asset rules (`[assets]`).
- Capability-specific typed source configurations:
  - `sources_external_household_only.toml`: maps novel columns, date formats, and sheet/table selectors into canonical Bronze household contracts (`HOUSEHOLD_CORE` only).
  - `sources_external_household_wealth.toml`: pairs external household evidence with external cash balance sheets (`HOUSEHOLD_CORE` + `WEALTH`).
- Dedicated runtime execution profiles:
  - `settings_external_household_only.toml`: defines `[capabilities] enabled = ["household_core"]`.
  - `settings_external_household_wealth.toml`: defines `[capabilities] enabled = ["household_core", "wealth"]`.

### Step 2 - Build Excel fixture/config
Run diagnostics first (`validate-config`, `check-sources`, `dry-run-admission`), then full household-only pipeline against `generic_accounts.xlsx`. Assert Pre-Bronze retains raw vendor layout while Bronze and Silver reflect normalized canonical financial contracts.

### Step 3 - Build CSV fixture/config
Run diagnostics and full household pipeline against `generic_expenses.csv`. Prove date parsing, string trimming, and column renaming normalize cleanly into Bronze.

### Step 4 - Build SQLite fixture/config
Run diagnostics and full household pipeline against `generic_household.sqlite`. Prove selector-driven table extraction without hardcoded `zcategory` assumptions.

### Step 5 - Cross-topology canonical equivalence & Analytical Output Assertions
Where fixtures represent the same financial scenario, compare canonical Bronze, Silver, and Gold analytical results:
- Sort by canonical identity to verify source provenance differs while financial meaning remains byte-for-byte identical.
- Assertive analytical outputs:
  - In `sources_external_household_only.toml`: verify `Total_Expense`, `Total_Income`, and `Net_Cashflow_Month` in Gold marts (`gold.household_monthly_summary`, `gold.household_cashflow_breakdown`, `gold.core_monthly_fact`) strictly equal the ground-truth mathematical sums of the external test records down to the cent.
  - In `sources_external_household_wealth.toml`: verify net worth, liquid asset totals, and balance sheet growth reflect external account balances without zero-filled investment placeholders.
  - Assert that all investment-related tables and columns are omitted physically from the warehouse.

### Step 6 - Identity certification
Excel/CSV derived IDs stable across reordered rows/reruns. SQLite trusted IDs preserved.

### Step 7 - Failure pack
For each relevant topology exercise malformed schema, invalid mapping and identity collision/duplicate grain. Diagnostics must fail before invalid canonical publication.

### Step 8 - Empty and incremental/change proof
For at least one configured optional/transaction dataset, certify a valid zero-row input and prove it is not treated as missing. Then modify one transaction/source artifact and verify only expected state changes according to policy.

### Step 9 - Recovery/backup smoke
At least one external fixture exercises failure rollback + backup/restore.

### Step 10 - Hidden-assumption sweep
Any production branch checking Shan path/table/category names fails this phase and is removed.

## 7. Files and symbols in scope

Create external household fixtures/configs and certification tests.

Modify production code only to remove genuine hidden assumptions exposed by supported fixtures. Any broad architecture change must be reflected back into ARCHITECTURE/earlier phase assumptions before acceptance.

## 8. Cross-cutting impacts

**Persistence:** each fixture gets isolated Control Plane/warehouse.

**Identity:** cross-topology identity semantics tested; exact IDs need not match between trusted-source and derived strategies unless configured key semantics intentionally make them equivalent.

**Provenance:** SourceId/artifact differs while canonical finance remains stable.

**Observability:** lineage reconstructable for at least one external fixture.

**Performance:** fixture scale is correctness-focused; no optimization based on tiny fixtures.

## 9. Tests and verification

Mandatory:
- Excel config-only onboarding;
- CSV config-only onboarding;
- non-Shan SQLite config-only onboarding;
- execution of headless runs across `sources_external_household_only.toml` and `sources_external_household_wealth.toml`;
- assertive verification of Gold analytical outputs: `Total_Expense`, `Total_Income`, and `Net_Cashflow_Month` in `gold.household_monthly_summary` strictly match external evidence ground truth;
- verification that investment tables and columns are strictly omitted from DuckDB;
- diagnostics pass before full run;
- no source code changes between fixtures;
- canonical scenario equivalence where designed;
- stable derived IDs;
- preserved trusted IDs;
- malformed schema/mapping/collision failures;
- valid empty configured dataset;
- incremental rerun;
- rollback/backup restore smoke;
- zero hidden Shan topology assumptions.

## 10. Explicit non-goals

Do not:
- build a UI/config wizard;
- weaken canonical contracts to make fixtures pass;
- add fixture-specific provider logic;
- change financial formulas;
- require investment evidence.

## 11. Completion checklist

- [ ] Canonical Bronze household schemas slimmed down to essential financial columns.
- [ ] Excel external household topology passes.
- [ ] CSV external household topology passes.
- [ ] SQLite external household topology passes.
- [ ] Declarative capability fixtures (`sources_external_household_only.toml`, `sources_external_household_wealth.toml`) authored and certified.
- [ ] End-to-end analytical outputs asserted against expected mathematical ground truth.
- [ ] No source-code customization required.
- [ ] Identity semantics correct.
- [ ] Failure diagnostics actionable.
- [ ] Incremental behavior correct.
- [ ] Hidden Shan assumptions zero.

## 12. Commit boundary

```text
test(certification): add external household topologies
```

## 13. Handoff to Phase 047

Phase 047 may assume household generalization is proven across multiple physical source types and identity strategies. It will apply the same external-user standard to domestic and foreign investment topologies and capability dependency failures.

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
