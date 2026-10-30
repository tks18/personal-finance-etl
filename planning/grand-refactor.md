# Personal Finance ETL — Grand Refactor Authoritative Implementation Plan

**Implementation authority:** `personal-finance-etl` v9.5.3 plus this specification  
**Scope:** main PFETL application only  
**Out of scope:** companion applications and documentation-platform implementation  
**Execution cadence:** each phase is intended for one 2–3 hour focused session unless marked as a certification phase  
**Golden oracle:** v9.5.3 financial values, deterministic IDs, persistence/recovery truth, observability lineage, and accepted performance envelope

> **Governing product invariant:** Users configure their evidence and capabilities. PFETL owns the financial meaning.

# PART I — HOW TO IMPLEMENT FROM THIS DOCUMENT

This is not a roadmap. Each phase is a commit boundary. Do not redesign the target while implementing. If code evidence contradicts a stated anchor, stop, amend this document, and add a prerequisite phase rather than stretching the current phase.

Every phase must end with a green repository. Dangerous migrations use **expand → migrate → verify → contract**. No demolition-first branches.

## Permanent invariants

1. `Settings`, `SourceConfiguration`, and `FinancialRules` remain separate concerns.
2. Raw Store / Control Plane owns received evidence and operational truth.
3. Pre-Bronze owns source-shaped tabular state.
4. Bronze owns PFETL canonical evidence.
5. Silver owns canonical reconstructed financial state.
6. Gold owns PFETL decision/analytical surfaces.
7. Users cannot define arbitrary Bronze/Silver/Gold schemas.
8. Bronze identity is dataset-specific.
9. PURCHASE, SALE, LOT, REALIZED, RECON_GROUP, RECON_EVENT, RECON_LOT_GROUP, and TAX IDs remain byte-stable for unchanged inputs.
10. Capability execution is plan-driven, never scattered `ENABLE_X` checks.
11. Observability emitter/sink architecture is frozen.
12. DuckDB-first / SQLite-second commit order and `RECOVERY_REQUIRED` semantics remain.
13. Shan's topology becomes ordinary configuration, never `legacy_mode`.
14. Every release remains independently releasable.

# PART II — CURRENT v9.5.3 BASELINE AND TARGET

## Current fixed source chain

```text
Settings paths + statement-folder names
        ↓
category strings
        ↓
FILE_TYPE_MAP + FileHashPolicy + Bronze sync category
        ↓
Control Plane Raw Store
        ↓
DataExtractor provider-specific methods
        ↓
ExtractionResult fixed fields
        ↓
Gatekeeper head(1) execution check
        ↓
Bronze source-shaped persistence
        ↓
TransformationDAG + market enrichments
        ↓
Quant → Tax → Wealth/FIRE
        ↓
all Silver + all Gold required every run
```

## Target core chain

```text
Settings + FinancialRules + versioned SourceConfiguration
        ↓
CapabilityPlanner → ExecutionPlan
        ↓
SourcePlanner → DatasetPlans
        ↓
Control Plane Raw Store
        ↓
provider registry + typed selector
        ↓
source-shaped frame
        ↓
Pandera source validation
        ↓
Pre-Bronze
        ↓
compiled mapping / normalization
        ↓
Bronze identity resolution where required
        ↓
PFETL-owned Pandera Bronze validation
        ↓
canonical Bronze DatasetCollection
        ↓
plan-driven transforms / engines
        ↓
active Silver / Gold contracts only
```

## Target contract ownership

- `contracts`: stable IDs/messages (`DatasetId`, `SourceId`, `CapabilityId`, `DatasetCollection`, validation/execution messages).
- `config`: user-authored Pydantic source/mapping/identity/change-policy/capability configuration.
- `application`: source planning, mapping compilation/execution coordination, capability planning, execution planning.
- `domain`: financial meaning and downstream financial identities.
- `infrastructure`: provider I/O, Pandera execution, Control Plane, Pre-Bronze/Bronze/Silver/Gold persistence.
- `bootstrap`: concrete dependency assembly.

# PART III — MIGRATION INVENTORIES

## Bronze source ledger

| Current stream | Category | Provider | Bronze table | Sync | Identity | Target disposition |
| --- | --- | --- | --- | --- | --- | --- |
| zcategory | sqlite_source | SQLite | bronze.r_SQLite_ZCategory | FULL_REPLACE | Preserve trusted source UID where required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| assetgroup | sqlite_source | SQLite | bronze.r_SQLite_AssetGroup | FULL_REPLACE | Preserve trusted source UID where required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| assets | sqlite_source | SQLite | bronze.r_SQLite_Assets | FULL_REPLACE | Preserve trusted source UID where required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| currency | sqlite_source | SQLite | bronze.r_SQLite_Currency | FULL_REPLACE | Preserve trusted source UID where required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| inoutcome | sqlite_source | SQLite | bronze.r_SQLite_InOutcome | FULL_REPLACE | Preserve trusted source UID where required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| stg_mf_isin_mapping | mf_isin | CSV | bronze.r_MF_ISIN_Mapping | FULL_REPLACE | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| stg_benchmark_mapping | benchmark_mapping | CSV | bronze.r_Benchmark_Mapping | FULL_REPLACE | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| raw_opening_balances | opening_balances | CSV | bronze.r_Opening_Balances | FULL_REPLACE | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| raw_benchmark_master | benchmark_master | CSV | bronze.r_Benchmark_Master | FULL_REPLACE | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| raw_macro_parameters | macro_parameters | CSV | bronze.r_Macro_Parameters | FULL_REPLACE | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| column_master | column_master | CSV | bronze.r_Column_Master | FULL_REPLACE | Define from canonical grain; derive only if required | Remove as data-plane dataset after mapping-config cutover |
| mf_market_data_raw | mf_holdings | Excel | bronze.r_MF_Market_Data | INCREMENTAL | No synthetic Bronze ID; retain later financial identity | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| us_stock_transactions_raw | us_stock_transactions | Excel | bronze.r_US_Stock_Transactions | INCREMENTAL | No synthetic Bronze ID; retain later financial identity | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| currency_mapping_raw | currency_mapping | CSV | bronze.r_Currency_Mapping | FULL_REPLACE | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| currency_fx_raw | currency_history | Provider/Internal | bronze.r_Currency_FX_Data | INCREMENTAL | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| mf_transactions_raw | mf_orders | Excel | bronze.r_MF_Transactions | INCREMENTAL | No synthetic Bronze ID; retain later financial identity | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| stock_market_data_raw | stock_pl | Excel | bronze.r_Stock_Market_Data | INCREMENTAL | No synthetic Bronze ID; retain later financial identity | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| stock_transactions_raw | stock_orders | Excel | bronze.r_Stock_Transactions | INCREMENTAL | No synthetic Bronze ID; retain later financial identity | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| benchmark_history_raw | benchmark_history | Provider/Internal | bronze.r_Benchmark_Data | INCREMENTAL | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |
| us_stock_market_data_raw | us_stock_market | Provider/Internal | bronze.r_US_Stock_Prices | INCREMENTAL | Define from canonical grain; derive only if required | Raw → Pre-Bronze → source validation → normalize → identity if required → Bronze validation → canonical Bronze |

## Silver contract ledger

| Contract | Physical table | Domain | Grain | Producer |
| --- | --- | --- | --- | --- |
| df_d_calendar | silver.d_Calendar | Common | Day | CoreEngine |
| df_d_income_category | silver.d_Income_Category | Wealth | Category | CoreEngine |
| df_d_income_subcategory | silver.d_Income_Subcategory | Wealth | Subcategory | CoreEngine |
| df_d_expense_category | silver.d_Expense_Category | Wealth | Category | CoreEngine |
| df_d_expense_subcategory | silver.d_Expense_Subcategory | Wealth | Subcategory | CoreEngine |
| df_d_asset_category | silver.d_Asset_Category | Wealth | Category | CoreEngine |
| df_d_asset_subcategory | silver.d_Asset_SubCategory | Wealth | Subcategory | CoreEngine |
| df_d_currency | silver.d_Currency | Common | Currency | CoreEngine |
| df_d_benchmark_master | silver.d_Investment_Benchmark_Master | Investments | Benchmark | CoreEngine |
| df_f_currency_fx_rates | silver.f_Currency_FX_Rates | Common | Date-Currency | CoreEngine |
| df_d_investment_master | silver.d_Investment_Master | Investments | ISIN | CoreEngine |
| df_d_macro_parameters | silver.d_Macro_Parameters | Investments | FinancialYear | CoreEngine |
| df_f_income_transactions | silver.f_Income_Transactions | Wealth | Transaction | CoreEngine |
| df_f_expense_transactions | silver.f_Expense_Transactions | Wealth | Transaction | CoreEngine |
| df_f_transfer_transactions | silver.f_Transfer_Transactions | Wealth | Transaction | CoreEngine |
| df_f_opening_balances | silver.f_Opening_Balances | Wealth | Balance | CoreEngine |
| df_f_investment_market_data | silver.f_Investment_Market_Data | Investments | Quote | CoreEngine |
| df_f_tf_inv_purchase | silver.f_Investment_Purchase_Data | Investments | Trade | CoreEngine |
| df_f_tf_inv_sale | silver.f_Investment_Sale_Data | Investments | Trade | CoreEngine |
| df_f_investment_benchmark_data | silver.f_Investment_Benchmark_Data | Investments | Quote | CoreEngine |
| df_f_investment_analytics_lot | silver.f_Investment_Analytics_Lot | Investments | ISIN-Lot | InvestmentQuantEngine |
| df_f_investment_realized_events | silver.f_Investment_Realized_Events | Investments | RealizedEvent | InvestmentQuantEngine |
| df_f_investment_reconciliation_events | silver.f_Investment_Reconciliation_Events | Investments | ReconEvent | InvestmentQuantEngine |
| df_f_tax_events | silver.f_Tax_Events | Taxes | TaxEvent | TaxEngine |

## Gold contract ledger

| Contract | Physical table | Domain | Grain | Producer |
| --- | --- | --- | --- | --- |
| df_p_tax_year_summary | gold.Tax_Year_Summary | Taxes | FY | TaxEngine |
| df_p_tax_income_breakdown | gold.Tax_Income_Breakdown | Taxes | FY-Head-SubHead-Source | TaxEngine |
| df_p_tax_reconciliation | gold.Tax_Reconciliation | Taxes | FY-SubHead | TaxEngine |
| df_p_tf_wealth_monthly_totals | gold.Core_Monthly_Fact | Wealth | Month | WealthPresentationEngine |
| df_p_tf_net_worth_monthly_summary | gold.Wealth_Asset_Breakdown | Wealth | Month-Asset | WealthPresentationEngine |
| df_p_tf_category_spend_analytics | gold.Cashflow_Expense_Breakdown | Wealth | Month-ExpenseCategory | WealthPresentationEngine |
| df_p_tf_income_streams_monthly | gold.Cashflow_Income_Breakdown | Wealth | Month-IncomeCategory | WealthPresentationEngine |
| df_p_tf_wealth_risk_analytics | gold.Wealth_FIRE_Analytics | Wealth | Month | WealthPresentationEngine |
| df_p_tf_budget_forecast_monthly | gold.Forecast_Budget_Variance | Wealth | Month | WealthPresentationEngine |
| df_p_tf_investment_analytics | gold.Investment_Portfolio_Summary | Investments | Month-ISIN | InvestmentQuantEngine |
| df_p_tf_monthly_cashflow_summary | gold.Cashflow_Efficiency_Analytics | Wealth | Month | WealthPresentationEngine |
| df_p_tf_cashflow_activity_summary | gold.Cashflow_Activity_Summary | Wealth | Month | WealthPresentationEngine |
| df_f_investment_analytics_isin | gold.Investment_By_ISIN | Investments | Date-ISIN | InvestmentQuantEngine |
| df_f_investment_analytics_subtype | gold.Investment_By_Subtype | Investments | Date-Subtype | InvestmentQuantEngine |
| df_f_investment_analytics_class | gold.Investment_By_Class | Investments | Date-Class | InvestmentQuantEngine |
| df_f_investment_analytics_instrument_type | gold.Investment_By_Instrument_Type | Investments | Date-InstrumentType | InvestmentQuantEngine |
| df_f_investment_analytics_sector | gold.Investment_By_Sector | Investments | Date-Sector | InvestmentQuantEngine |
| df_f_investment_analytics_industry | gold.Investment_By_Industry | Investments | Date-Industry | InvestmentQuantEngine |
| df_f_investment_analytics_portfolio | gold.Investment_By_Portfolio | Investments | Date | InvestmentQuantEngine |
| df_f_investment_analytics_geo | gold.Investment_By_Geo | Investments | Date-Geo | InvestmentQuantEngine |
| df_f_investment_analytics_country | gold.Investment_By_Country | Investments | Date-Country | InvestmentQuantEngine |
| df_f_investment_analytics_currency | gold.Investment_By_Currency | Investments | Date-Currency | InvestmentQuantEngine |

## Protected identity ledger

| Identity | Current owner | Target rule |
|---|---|---|
| Household UID/ZUID family | source SQLite + household transforms | preserve trusted IDs; alternative users may derive Bronze IDs only where canonical contract requires |
| PURCHASE / SALE | investment transforms | remain downstream financial identity |
| LOT / REALIZED | FIFO | remain reconstruction identity |
| RECON_* | reconciliation | remain reconciliation identity |
| TAX | Tax event hashing | remain Tax identity |
| future Bronze derived ID | new identity-resolution service | separate namespace; canonical evidence identity only |

# PART IV — IMPLEMENTATION RELEASE TRAIN

# v9.5.4 — Stable Dataset Identity

## 9.5.4-A — Introduce `DatasetId` additively

**Purpose**  
Separate logical dataset identity from `ExtractionResult` attributes, frame keys, and physical tables.

**Current implementation anchors**
- `infrastructure/warehouse/contracts.py::BronzeDataContract`
- `infrastructure/warehouse/contracts.py::DataContract`
- `infrastructure/warehouse/registry.py`

**Exact state required after this phase**  
Every Bronze/Silver/Gold registry row carries a typed `DatasetId`; all existing keys/tables remain unchanged.

**Implementation sequence**
1. Create `contracts/datasets.py` with string-backed `DatasetId`.
2. Add `dataset_id` to both warehouse contract dataclasses.
3. Populate all 20 Bronze, 24 Silver and 22 Gold entries.
4. Add registry uniqueness/layer validation.
5. Do not migrate any runtime lookup yet.

**Files / symbols expected to change**
- `contracts/datasets.py (new)`
- `infrastructure/warehouse/contracts.py`
- `infrastructure/warehouse/registry.py`
- `tests covering registry constitution`

**Temporary coexistence / compatibility state**  
`DatasetId` is canonical; `extraction_attribute`/`contract_id` remain compatibility identities.

**Tests and assertions**
- [ ] Registry counts remain 20/24/22.
- [ ] Every contract has exactly one DatasetId.
- [ ] No duplicate DatasetId.
- [ ] Existing contract/frame lookup still returns the same contract.
- [ ] No physical table name changes.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not rename frames or tables.
- Do not modify ExtractionResult.
- Do not introduce source configuration.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.4-B — Add DatasetId registry indexes

**Purpose**  
Allow new code to depend on stable identity before old callers migrate.

**Current implementation anchors**
- `infrastructure/warehouse/registry.py`

**Exact state required after this phase**  
Registry supports lookup/enumeration by DatasetId while preserving existing APIs.

**Implementation sequence**
1. Build immutable indexes at module initialization or validation time.
2. Add `get_contract(dataset_id)` and Bronze-specific lookup.
3. Add layer enumeration returning DatasetIds.
4. Fail deterministically for unknown/duplicate IDs.

**Files / symbols expected to change**
- `infrastructure/warehouse/registry.py`
- `registry tests`

**Temporary coexistence / compatibility state**  
Old and new lookup APIs coexist.

**Tests and assertions**
- [ ] Lookup each layer by DatasetId.
- [ ] Unknown DatasetId raises the documented error.
- [ ] Index order does not alter publication order.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.4-C — Version the registry fingerprint

**Purpose**  
Make semantic dataset identity visible to Meta without conflating it with storage naming.

**Current implementation anchors**
- `infrastructure/warehouse/meta/layer.py`
- `registry fingerprint helper used by Meta`

**Exact state required after this phase**  
Meta fingerprint deterministically includes DatasetId and explicitly documents semantic vs physical fields.

**Implementation sequence**
1. Trace current fingerprint fields.
2. Add DatasetId and deterministic DatasetId ordering.
3. Version fingerprint payload if shape changes.
4. Update fingerprint regression fixture.

**Files / symbols expected to change**
- `infrastructure/warehouse/meta/layer.py`
- `infrastructure/warehouse/registry.py`
- `Meta tests`

**Temporary coexistence / compatibility state**  
No warehouse DDL changes.

**Tests and assertions**
- [ ] Repeated fingerprint is stable.
- [ ] Registry reorder does not change fingerprint.
- [ ] Intentional DatasetId change does change fingerprint.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.5.5 — Source Descriptor Vocabulary

## 9.5.5-A — Introduce `SourceId` and `ProviderType`

**Purpose**  
Separate physical source identity from category strings such as `sqlite_source` and `mf_orders`.

**Current implementation anchors**
- `infrastructure/providers/files/locator.py::_match_category`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `infrastructure/control_plane/hashing.py::FILE_TYPE_MAP`

**Exact state required after this phase**  
Runtime vocabulary can name a source independently from CSV/Excel/SQLite provider type.

**Implementation sequence**
1. Create `contracts/sources.py`.
2. Define `SourceId` validated/string-backed type.
3. Define `ProviderType` limited initially to CSV, EXCEL, SQLITE.
4. Create test fixtures mapping current sources to provider types.

**Files / symbols expected to change**
- `contracts/sources.py`
- `contracts exports`
- `tests`

**Temporary coexistence / compatibility state**  
Category strings remain runtime authority for now.

**Tests and assertions**
- [ ] Two different SourceIds may both use EXCEL.
- [ ] ProviderType has no financial categories.
- [ ] No discovery behavior changes.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.5-B — Define `SourceConfig`

**Purpose**  
Move future source-level facts into a typed user configuration model.

**Current implementation anchors**
- `config/settings.py source path fields`

**Exact state required after this phase**  
Pydantic `SourceConfig` owns source ID, provider type, location, enabled state, optional description/default change policy reference.

**Implementation sequence**
1. Create `config/sources/model.py`.
2. Define source location representation without financial semantics.
3. Add serialization/round-trip validation.
4. Model current household SQLite, one Excel, and one CSV source in tests.

**Files / symbols expected to change**
- `config/sources/model.py`
- `config/sources/__init__.py`
- `tests`

**Temporary coexistence / compatibility state**  
Existing Settings paths remain authoritative until later cutover.

**Tests and assertions**
- [ ] Duplicate SourceIds rejected at aggregate validation.
- [ ] Location survives round trip.
- [ ] No provider I/O occurs in model validation.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.5-C — Define typed selectors

**Purpose**  
Move table/sheet selection into provider-compatible configuration.

**Current implementation anchors**
- `infrastructure/providers/files/sqlite.py::SQLiteExtractor.extract_base_tables`
- `infrastructure/providers/files/excel.py dataset-specific extractors`

**Exact state required after this phase**  
CSV/Excel/SQLite selectors are discriminated typed models and contain only physical selection/parsing facts.

**Implementation sequence**
1. Create `config/sources/selectors.py`.
2. Define `CsvSelector`, `ExcelSelector`, `SqliteSelector`.
3. Validate selector/provider compatibility in SourceDatasetConfig helper/test.
4. Do not allow arbitrary SQL initially.

**Files / symbols expected to change**
- `config/sources/selectors.py`
- `tests`

**Temporary coexistence / compatibility state**  
Existing extractors still choose fixed tables/sheets.

**Tests and assertions**
- [ ] SQLite selector requires table name.
- [ ] Excel selector requires supported sheet semantics.
- [ ] Provider-selector mismatch rejected.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.5-D — Define `SourceDatasetConfig`

**Purpose**  
Represent one canonical dataset supplied by one configured source.

**Current implementation anchors**
- `contracts/extraction.py::ExtractionResult`
- `BRONZE_CONTRACT_REGISTRY`

**Exact state required after this phase**  
Each configured external dataset binds SourceId + DatasetId + selector, with placeholders/references for mapping, identity and change policy.

**Implementation sequence**
1. Create model with `source_id`, `dataset_id`, `selector`, `enabled`, optional policy/mapping references.
2. Validate referenced source exists at aggregate level.
3. Validate `(source_id,dataset_id)` uniqueness.
4. Validate DatasetId is externally sourceable Bronze contract.

**Files / symbols expected to change**
- `config/sources/model.py`
- `tests`

**Temporary coexistence / compatibility state**  
No runtime consumption.

**Tests and assertions**
- [ ] Duplicate bindings fail.
- [ ] Unknown source fails.
- [ ] Gold/Silver DatasetId cannot be configured as source evidence.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.5-E — Encode Shan topology completely

**Purpose**  
Prove the target source vocabulary can describe all v9.5.3 external evidence before runtime migration.

**Current implementation anchors**
- `config/settings.py`
- `infrastructure/providers/files/locator.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `BRONZE_CONTRACT_REGISTRY`

**Exact state required after this phase**  
A versioned test/example configuration represents every externally sourced current Bronze dataset; provider-generated history is explicitly classified separately.

**Implementation sequence**
1. Create a canonical Shan source-config fixture.
2. Represent five SQLite household tables as separate dataset bindings on one source.
3. Represent each statement category as configured Excel evidence.
4. Represent current CSV assets as configured sources/datasets.
5. Mark currency/benchmark/US market history as provider-generated/internal where appropriate.
6. Add set-equivalence test against sourceable Bronze DatasetIds.

**Files / symbols expected to change**
- `tests/fixtures/source configuration`
- `source-config coverage test`

**Temporary coexistence / compatibility state**  
Runtime still uses Settings + locator + injection.

**Tests and assertions**
- [ ] Every external current Bronze DatasetId appears exactly once.
- [ ] No internal/provider-generated dataset is falsely required as user file.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.5.6 — Change Detection Policy

## 9.5.6-A — Define resolved change policy

**Purpose**  
Replace one format boolean with explicit fingerprint/drift/rename/sync semantics.

**Current implementation anchors**
- `config/settings.py::FileHashPolicy`
- `infrastructure/control_plane/hashing.py::FILE_TYPE_MAP`
- `BRONZE_CONTRACT_REGISTRY.is_full_replace`

**Exact state required after this phase**  
Configuration can express fingerprint, drift, rename and sync independently.

**Implementation sequence**
1. Create enums/models for fingerprint, drift, rename and sync.
2. Add validation: content drift/rename requires fingerprint.
3. Do not wire runtime.

**Files / symbols expected to change**
- `config/sources/change_detection.py`
- `tests`

**Temporary coexistence / compatibility state**  
FileHashPolicy remains active.

**Tests and assertions**
- [ ] Invalid policy combinations rejected.
- [ ] Provider type is absent from policy semantics.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.6-B — Compatibility policy resolver

**Purpose**  
Prove new policy exactly represents current behavior.

**Current implementation anchors**
- `Settings.FILE_HASH_POLICY`
- `FILE_TYPE_MAP`
- `BRONZE_CONTRACT_REGISTRY`

**Exact state required after this phase**  
One resolver returns a complete resolved policy for every current category/dataset.

**Implementation sequence**
1. Translate current hash booleans into fingerprint/drift.
2. Translate full-replace flag into sync strategy.
3. Preserve current rename-by-content requirements.
4. Snapshot all current category policies in parameterized tests.

**Files / symbols expected to change**
- `application/ingestion/change_policy.py or equivalent`
- `tests`

**Temporary coexistence / compatibility state**  
Runtime still calls old sync API.

**Tests and assertions**
- [ ] All current categories resolve.
- [ ] Resolved policy matches v9.5.3 behavior.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.6-C — Make FileSyncService policy-driven

**Purpose**  
Move hash/change decisions out of category/provider inference.

**Current implementation anchors**
- `infrastructure/control_plane/file_sync.py::_sync_with_disk`
- `infrastructure/control_plane/hashing.py::FILE_TYPE_MAP`

**Exact state required after this phase**  
File sync receives resolved policy for each actionable source/dataset; category remains temporary grouping metadata only.

**Implementation sequence**
1. Add resolved-policy input to sync boundary.
2. Change hash requirement decision to policy.
3. Preserve current category grouping for registry compatibility.
4. Migrate PipelineExecutor caller through compatibility resolver.
5. Test NEW/CHANGED/UNCHANGED/RENAME/REMOVED/full-replace.

**Files / symbols expected to change**
- `infrastructure/control_plane/file_sync.py`
- `application/pipeline/execution.py`
- `change-policy resolver`
- `tests`

**Temporary coexistence / compatibility state**  
Category still exists in cp_file_registry and Bronze registry.

**Tests and assertions**
- [ ] All sync-state tests pass.
- [ ] Rename behavior unchanged.
- [ ] Control Plane rows unchanged except no policy derivation from type.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run file-sync focused benchmark only if hashing path changes materially.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.6-D — Remove hash-policy authority from `FILE_TYPE_MAP`

**Purpose**  
Finish policy ownership migration.

**Current implementation anchors**
- `infrastructure/warehouse/meta/layer.py`
- `infrastructure/control_plane/artifact_repository.py`
- `infrastructure/control_plane/hashing.py`

**Exact state required after this phase**  
No production policy decision depends on CSV/Excel/SQLite type.

**Implementation sequence**
1. Migrate Meta/artifact consumers to resolved policy.
2. Search repository for FILE_HASH_POLICY/FILE_TYPE_MAP policy reads.
3. Rename/reduce FILE_TYPE_MAP if retained only as descriptive provider metadata.
4. Add architecture grep/test preventing provider-type hash branching.

**Files / symbols expected to change**
- `Meta layer`
- `artifact repository`
- `hashing module`
- `tests`

**Temporary coexistence / compatibility state**  
Physical file type may remain descriptive metadata.

**Tests and assertions**
- [ ] Zero policy decisions use provider type.
- [ ] Full sync regression passes.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete obsolete FileHashPolicy compatibility resolver only after SourceConfiguration becomes runtime authority.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.5.7 — Bronze Identity Policy Foundation

## 9.5.7-A — Declare Bronze identity requirements

**Purpose**  
Make identity requirement PFETL-owned per canonical dataset.

**Current implementation anchors**
- `infrastructure/warehouse/contracts.py::BronzeDataContract`
- `domain/common/identity.py`

**Exact state required after this phase**  
Every Bronze contract explicitly declares whether stable Bronze identity is required and its uniqueness/grain expectation.

**Implementation sequence**
1. Add `identity_requirement` enum and uniqueness/grain metadata to canonical Bronze contract metadata.
2. Classify all 20 Bronze rows.
3. Preserve investment evidence as no universal Bronze ID where identity is later financial.
4. Mark household contracts requiring stable source keys explicitly.

**Files / symbols expected to change**
- `contracts/datasets.py or dedicated identity contract`
- `warehouse/contracts.py`
- `registry tests`

**Temporary coexistence / compatibility state**  
No IDs are generated yet.

**Tests and assertions**
- [ ] No Bronze contract has implicit/default unknown identity policy.
- [ ] Investment raw evidence is not forced into synthetic identity.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.7-B — Define user identity strategies

**Purpose**  
Define how a user may satisfy a required Bronze identity.

**Current implementation anchors**
- `domain/common/identity.py canonical serialization`

**Exact state required after this phase**  
Pydantic discriminated union supports trusted source field, composite fields and deterministic derived identity.

**Implementation sequence**
1. Create `config/sources/identity.py`.
2. Define strategy models and namespace/version fields where needed.
3. Reject row index, timestamp, randomness and Python hash semantics by construction.
4. Validate referenced fields syntactically.

**Files / symbols expected to change**
- `config/sources/identity.py`
- `tests`

**Temporary coexistence / compatibility state**  
No production execution.

**Tests and assertions**
- [ ] All strategy variants round-trip.
- [ ] Invalid/empty field lists rejected.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.7-C — Compile identity plans

**Purpose**  
Combine PFETL requirement + user strategy + mapping output into executable intent.

**Current implementation anchors**
- `SourceDatasetConfig`
- `Bronze identity metadata`

**Exact state required after this phase**  
Application compiler emits immutable identity plan or fails before ingestion.

**Implementation sequence**
1. Implement compiler.
2. REQUIRED + none => error.
3. NONE + none => valid.
4. Verify strategy fields exist after mapping.
5. Reserve new Bronze namespaces distinct from protected financial namespaces.

**Files / symbols expected to change**
- `application/ingestion/identity_resolution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Executor still not wired into Bronze.

**Tests and assertions**
- [ ] Missing required identity fails.
- [ ] Investment no-ID dataset compiles successfully without strategy.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.5.7-D — Implement deterministic Bronze identity executor

**Purpose**  
Prove configurable identity generation independently of persistence.

**Current implementation anchors**
- `domain/common/identity.py::canonicalize_value`
- `domain/common/identity.py::generate_deterministic_id`

**Exact state required after this phase**  
Executor generates stable IDs from normalized canonical fields using the established canonicalization philosophy without modifying existing financial namespace contracts.

**Implementation sequence**
1. Implement executor against small Polars frames.
2. Use separate Bronze namespace convention.
3. Detect duplicate generated IDs and return typed collision failure.
4. Add normalization/order stability tests.

**Files / symbols expected to change**
- `application/ingestion/identity_resolution.py`
- `tests`

**Temporary coexistence / compatibility state**  
No current pipeline calls executor.

**Tests and assertions**
- [ ] Repeated input yields identical ID.
- [ ] Field order does not alter ID.
- [ ] Identity-field change alters ID.
- [ ] Collision is explicit failure.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.6.x — Canonical Silver/Gold Vocabulary Migration

## 9.6.0-A — Freeze Silver grains and identity semantics

**Purpose**  
Review all 24 Silver contracts; replace vague grain metadata with exact one-row meaning; record identity key/natural grain in registry migration metadata; no DDL changes.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Review all 24 Silver contracts; replace vague grain metadata with exact one-row meaning; record identity key/natural grain in registry migration metadata; no DDL changes.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Review all 24 Silver contracts is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.0-B — Create column disposition manifest

**Purpose**  
Parse all 533 Silver columns and classify canonical financial, canonical identity, provenance, source taxonomy, provider metadata, or implementation residue. Every column must have a disposition before schema migration.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Parse all 533 Silver columns and classify canonical financial, canonical identity, provenance, source taxonomy, provider metadata, or implementation residue. Every column must have a disposition before schema migration.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Parse all 533 Silver columns and classify canonical financial, canonical identity, provenance, source taxonomy, provider metadata, or implementation residue. Every column must have a disposition before schema migration. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.0-C — Create Gold dependency manifest

**Purpose**  
For all 22 Gold contracts, record exact Silver inputs/columns and presentation consumers so Silver renames have a deterministic blast-radius list.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. For all 22 Gold contracts, record exact Silver inputs/columns and presentation consumers so Silver renames have a deterministic blast-radius list.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] For all 22 Gold contracts, record exact Silver inputs/columns and presentation consumers so Silver renames have a deterministic blast-radius list. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.1-A — Introduce canonical foreign/US financial classification

**Purpose**  
Trace `__file_category__ == "US Stocks"`; choose existing financial attributes or add one narrow canonical classification; populate alongside source category.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Trace `__file_category__ == "US Stocks"`; choose existing financial attributes or add one narrow canonical classification; populate alongside source category.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Trace `__file_category__ == "US Stocks"` is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.1-B — Migrate PipelineExecutor US-range logic

**Purpose**  
Replace `_resolve_us_market_range` source-category filtering with canonical classification; assert identical date range on Shan data.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Replace `_resolve_us_market_range` source-category filtering with canonical classification; assert identical date range on Shan data.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Replace `_resolve_us_market_range` source-category filtering with canonical classification is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.1-C — Migrate market sync classification

**Purpose**  
Use the same canonical classification in `application/ingestion/market_sync.py`; no duplicate rule.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Use the same canonical classification in `application/ingestion/market_sync.py`; no duplicate rule.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Use the same canonical classification in `application/ingestion/market_sync.py` is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.1-D — Remove source-category decisions from investment domain

**Purpose**  
Migrate transforms/valuation; add architecture test forbidding financial branching on `__file_category__` under domain.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Migrate transforms/valuation; add architecture test forbidding financial branching on `__file_category__` under domain.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Migrate transforms/valuation is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.2-A — Introduce explicit artifact provenance reference

**Purpose**  
Define artifact/source/dataset provenance key sufficient for lineage while leaving Bronze operational `__file_name__` untouched.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Define artifact/source/dataset provenance key sufficient for lineage while leaving Bronze operational `__file_name__` untouched.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Define artifact/source/dataset provenance key sufficient for lineage while leaving Bronze operational `__file_name__` untouched. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.2-B — Populate provenance reference in canonical outputs

**Purpose**  
Dual-populate new provenance reference and old path fields; prove Control Plane lookup reconstructs file/path metadata.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Dual-populate new provenance reference and old path fields; prove Control Plane lookup reconstructs file/path metadata.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Dual-populate new provenance reference and old path fields is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.2-C — Migrate Silver/Gold lineage consumers

**Purpose**  
Replace legitimate `__file_name__`/`__folder_path__` reads with provenance reference; keep operational Bronze use.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Replace legitimate `__file_name__`/`__folder_path__` reads with provenance reference; keep operational Bronze use.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Replace legitimate `__file_name__`/`__folder_path__` reads with provenance reference is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.2-D — Remove source path fields from Silver

**Purpose**  
Delete from Silver DDL/producers only after zero financial/Gold consumers; retain operational provenance below Silver.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Delete from Silver DDL/producers only after zero financial/Gold consumers; retain operational provenance below Silver.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Delete from Silver DDL/producers only after zero financial/Gold consumers is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.3-A — Introduce provider-neutral market symbol

**Purpose**  
Separate canonical security/market symbol from `yF_Ticker`/`YAHOO_TICKER`; provider mapping retains Yahoo symbol.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Separate canonical security/market symbol from `yF_Ticker`/`YAHOO_TICKER`; provider mapping retains Yahoo symbol.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Separate canonical security/market symbol from `yF_Ticker`/`YAHOO_TICKER` is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.3-B — Migrate FX/benchmark/US provider consumers

**Purpose**  
Providers resolve their own symbol from mapping; canonical dimensions/facts use neutral field.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Providers resolve their own symbol from mapping; canonical dimensions/facts use neutral field.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Providers resolve their own symbol from mapping is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.3-C — Remove provider-specific symbols from canonical Silver

**Purpose**  
Delete only after providers, market sync and Gold consumers migrate.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Delete only after providers, market sync and Gold consumers migrate.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Delete only after providers, market sync and Gold consumers migrate. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.4-A — Household canonical column aliases

**Purpose**  
Add canonical names for household columns marked rename; values dual-populated and equality-tested.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Add canonical names for household columns marked rename; values dual-populated and equality-tested.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Add canonical names for household columns marked rename is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.4-B — Migrate household domain consumers

**Purpose**  
Income/expense/assets/transactions consume canonical names.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Income/expense/assets/transactions consume canonical names.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Income/expense/assets/transactions consume canonical names. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.4-C — Investment canonical column aliases and consumers

**Purpose**  
Repeat expand/migrate for investment dimensions/facts.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Repeat expand/migrate for investment dimensions/facts.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Repeat expand/migrate for investment dimensions/facts. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.4-D — Tax/wealth/FIRE consumer migration

**Purpose**  
Move downstream engines to canonical Silver vocabulary without formula changes.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Move downstream engines to canonical Silver vocabulary without formula changes.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Move downstream engines to canonical Silver vocabulary without formula changes. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.4-E — Gold producer migration

**Purpose**  
All Gold producers consume canonical Silver names; Gold values unchanged.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. All Gold producers consume canonical Silver names; Gold values unchanged.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] All Gold producers consume canonical Silver names is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.4-F — Contract deprecated Silver names

**Purpose**  
Remove aliases/source-native residue only after repository-wide zero references.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Remove aliases/source-native residue only after repository-wide zero references.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Remove aliases/source-native residue only after repository-wide zero references. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.5-A — Normalize Gold DatasetIds/domain taxonomy

**Purpose**  
Separate semantic Gold identity from historical `df_*` names and correct domain ownership.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Separate semantic Gold identity from historical `df_*` names and correct domain ownership.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Separate semantic Gold identity from historical `df_*` names and correct domain ownership. is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.6.5-B — Freeze Gold grains/dependencies

**Purpose**  
Add contract tests for each Gold row grain and Silver dependency; no analytical formula change.

**Current implementation anchors**
- `infrastructure/warehouse/schema/silver.py`
- `infrastructure/warehouse/contracts.py`
- `relevant domain/application consumers`

**Exact state required after this phase**  
The named migration responsibility is fully moved to canonical vocabulary while unrelated contracts remain unchanged.

**Implementation sequence**
1. Add contract tests for each Gold row grain and Silver dependency; no analytical formula change.
2. Update only the affected producer/consumer family.
3. Add exact-value or exact-selection regression tests before removing old vocabulary.

**Files / symbols expected to change**
- `listed anchors plus only affected producer/consumer modules`

**Temporary coexistence / compatibility state**  
Old and new fields coexist only where the phase explicitly requires expand/migrate.

**Tests and assertions**
- [ ] Add contract tests for each Gold row grain and Silver dependency is covered by focused tests.
- [ ] Shan real-data values are unchanged for affected outputs.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete old field/path only in the explicitly named contract phase after zero production references.

**Explicit non-goals**
- Do not change financial formulas.
- Do not generalize source ingestion in this release family.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.7.x — Capability Graph and Execution Planning

## 9.7.0-A — Derive exact CapabilityId set

**Purpose**  
Inspect TransformationDAG, market sync, Quant, Tax, Wealth and FIRE; define capability IDs from actual execution ownership, including optional enrichments.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Inspect TransformationDAG, market sync, Quant, Tax, Wealth and FIRE; define capability IDs from actual execution ownership, including optional enrichments.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Inspect TransformationDAG, market sync, Quant, Tax, Wealth and FIRE passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.0-B — Define CapabilityDescriptor

**Purpose**  
Fields: required capabilities, required/optional Bronze datasets, produced Silver/Gold datasets, required external enrichments. No callables.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Fields: required capabilities, required/optional Bronze datasets, produced Silver/Gold datasets, required external enrichments. No callables.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Fields: required capabilities, required/optional Bronze datasets, produced Silver/Gold datasets, required external enrichments. No callables. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.0-C — Encode full-current graph

**Purpose**  
Represent v9.5.3 full run and prove resolved active contract set equals all current 46 analytical contracts.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Represent v9.5.3 full run and prove resolved active contract set equals all current 46 analytical contracts.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Represent v9.5.3 full run and prove resolved active contract set equals all current 46 analytical contracts. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.1-A — Define immutable ExecutionPlan

**Purpose**  
Include fingerprint, requested/resolved capabilities, required source/Bronze datasets, active Silver/Gold, enrichments, ordered stages.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Include fingerprint, requested/resolved capabilities, required source/Bronze datasets, active Silver/Gold, enrichments, ordered stages.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Include fingerprint, requested/resolved capabilities, required source/Bronze datasets, active Silver/Gold, enrichments, ordered stages. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.1-B — Implement CapabilityPlanner

**Purpose**  
Topological resolution, cycle detection, missing configured dataset detection; no execution.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Topological resolution, cycle detection, missing configured dataset detection; no execution.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Topological resolution, cycle detection, missing configured dataset detection passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.1-C — Inject full plan into PipelineExecutor

**Purpose**  
Default plan is current full universe; execution still unconditional.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Default plan is current full universe; execution still unconditional.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Default plan is current full universe passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.1-D — Replace global completeness check

**Purpose**  
`execution.py` validates produced subset/required set against plan rather than entire registry.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. `execution.py` validates produced subset/required set against plan rather than entire registry.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] `execution.py` validates produced subset/required set against plan rather than entire registry. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.1-E — Persist plan fingerprint/context

**Purpose**  
Add run provenance and observability context without changing emitter architecture.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Add run provenance and observability context without changing emitter architecture.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Add run provenance and observability context without changing emitter architecture. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.2-A — Select first optional enrichment

**Purpose**  
Choose lowest-risk enrichment from actual graph; document exact inputs/outputs.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Choose lowest-risk enrichment from actual graph; document exact inputs/outputs.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Choose lowest-risk enrichment from actual graph passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.2-B — Make its orchestration plan-driven

**Purpose**  
Only PipelineExecutor/orchestration branches on plan; domain does not read config flags.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Only PipelineExecutor/orchestration branches on plan; domain does not read config flags.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Only PipelineExecutor/orchestration branches on plan passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.2-C — Make its publication plan-aware

**Purpose**  
Inactive contracts are omitted from Silver/Gold publication for this proof capability.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Inactive contracts are omitted from Silver/Gold publication for this proof capability.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Inactive contracts are omitted from Silver/Gold publication for this proof capability. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.7.2-D — End-to-end enabled/disabled proof

**Purpose**  
Disabled run omits only intended outputs and leaves unrelated values identical.

**Current implementation anchors**
- `application/pipeline/execution.py::run_engines`
- `application/pipeline/execution.py::_run_analytics_phase`
- `infrastructure/warehouse/contracts.py`

**Exact state required after this phase**  
Capability/execution responsibility described by the phase is explicit and testable.

**Implementation sequence**
1. Disabled run omits only intended outputs and leaves unrelated values identical.
2. Update capability/plan tests.
3. Keep full-current plan as compatibility default until source configuration cutover.

**Files / symbols expected to change**
- `contracts/capabilities.py (as applicable)`
- `application/pipeline/capability_planner.py`
- `application/pipeline/execution.py`
- `tests`

**Temporary coexistence / compatibility state**  
Full-current behavior remains default; partial plan is additive until optional proof phase.

**Tests and assertions**
- [ ] Disabled run omits only intended outputs and leaves unrelated values identical. passes focused tests.
- [ ] Full Shan plan still requires/produces all current contracts.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not add scattered feature flags.
- Do not migrate source topology yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.8.x — Versioned Source Configuration and Mapping

## 9.8.0-A — Define root SourceConfiguration

**Purpose**  
schema_version + sources + datasets + capability selection; FinancialRules excluded.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. schema_version + sources + datasets + capability selection; FinancialRules excluded.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] schema_version + sources + datasets + capability selection is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.0-B — Implement loader and semantic validation

**Purpose**  
Parse TOML/YAML/JSON according to chosen existing project convention; reject unknown schema version, duplicate IDs and broken references.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Parse TOML/YAML/JSON according to chosen existing project convention; reject unknown schema version, duplicate IDs and broken references.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Parse TOML/YAML/JSON according to chosen existing project convention is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.0-C — Integrate change and identity policies

**Purpose**  
SourceDatasetConfig resolves dataset override → source default → PFETL default where allowed.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. SourceDatasetConfig resolves dataset override → source default → PFETL default where allowed.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] SourceDatasetConfig resolves dataset override → source default → PFETL default where allowed. is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.0-D — Promote Shan fixture to real configuration

**Purpose**  
Represent all current external sources in a checked-in example/test config; runtime still old path.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Represent all current external sources in a checked-in example/test config; runtime still old path.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Represent all current external sources in a checked-in example/test config is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.1-A — Define column mapping model

**Purpose**  
Explicit source_field → canonical_field; target must exist in Bronze contract.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Explicit source_field → canonical_field; target must exist in Bronze contract.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Explicit source_field → canonical_field is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.1-B — Define bounded normalization rules

**Purpose**  
Cast/date/trim/case/default/null only; no eval/Python callbacks.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Cast/date/trim/case/default/null only; no eval/Python callbacks.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Cast/date/trim/case/default/null only is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.1-C — Implement mapping compiler

**Purpose**  
Configuration → immutable ordered normalization plan; no I/O.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Configuration → immutable ordered normalization plan; no I/O.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Configuration → immutable ordered normalization plan is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.1-D — Implement Polars normalization executor

**Purpose**  
Execute compiled plan on source-shaped frames; errors typed with dataset/field/rule.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Execute compiled plan on source-shaped frames; errors typed with dataset/field/rule.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Execute compiled plan on source-shaped frames is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.1-E — Integrate identity plan after normalization

**Purpose**  
Derived IDs consume canonical normalized values; collision is admission failure.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Derived IDs consume canonical normalized values; collision is admission failure.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Derived IDs consume canonical normalized values is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.2-A — Deterministic SourceConfiguration fingerprint

**Purpose**  
Canonical serialization covers sources, selectors, mappings, normalization, identity, change policy, capabilities.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Canonical serialization covers sources, selectors, mappings, normalization, identity, change policy, capabilities.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Canonical serialization covers sources, selectors, mappings, normalization, identity, change policy, capabilities. is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.2-B — Persist source-config snapshot in Control Plane

**Purpose**  
Add additive snapshot table/reference or extend snapshot model without merging FinancialRules.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Add additive snapshot table/reference or extend snapshot model without merging FinancialRules.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Add additive snapshot table/reference or extend snapshot model without merging FinancialRules. is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.8.2-C — Add config/source/dataset observability context

**Purpose**  
Extend context/event semantics only; no sink redesign.

**Current implementation anchors**
- `config/settings.py`
- `application/pipeline/execution.py::_inject_configuration_assets`
- `application/ingestion/coordinator.py`

**Exact state required after this phase**  
The named configuration responsibility exists as a typed, validated contract but old runtime topology remains until v9.9/v10 migration.

**Implementation sequence**
1. Extend context/event semantics only; no sink redesign.
2. Add round-trip and invalid-config tests.
3. Keep runtime source paths in Settings until explicit cutover phase.

**Files / symbols expected to change**
- `config/sources/*`
- `contracts/datasets.py`
- `contracts/sources.py`
- `tests`

**Temporary coexistence / compatibility state**  
New configuration and old Settings topology coexist; no dual financial semantics.

**Tests and assertions**
- [ ] Extend context/event semantics only is validated.
- [ ] FinancialRules serialization/fingerprint remains separate.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not create Pre-Bronze yet unless phase explicitly says so.
- Do not remove current Settings source fields yet.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v9.9.x — Pre-Bronze, Pandera, and First Vertical Migration

## 9.9.0-A — Add `pre_bronze` schema

**Purpose**  
Create DuckDB schema/bootstrap only; no data.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Create DuckDB schema/bootstrap only; no data.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Create DuckDB schema/bootstrap only passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.0-B — Define PreBronzeDataContract

**Purpose**  
DatasetId + physical table + sync strategy + provenance requirements; no canonical financial schema.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. DatasetId + physical table + sync strategy + provenance requirements; no canonical financial schema.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] DatasetId + physical table + sync strategy + provenance requirements passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.0-C — Implement full-replace PreBronze persistence

**Purpose**  
Persist source-shaped frame with artifact/source provenance.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Persist source-shaped frame with artifact/source provenance.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Persist source-shaped frame with artifact/source provenance. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.0-D — Implement incremental PreBronze persistence

**Purpose**  
Support changed-artifact replacement using explicit artifact provenance, not filename as sole identity.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Support changed-artifact replacement using explicit artifact provenance, not filename as sole identity.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Support changed-artifact replacement using explicit artifact provenance, not filename as sole identity. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.0-E — Integrate transaction lifecycle

**Purpose**  
Pre-Bronze writes share run-wide DuckDB transaction.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Pre-Bronze writes share run-wide DuckDB transaction.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Pre-Bronze writes share run-wide DuckDB transaction. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.0-F — Integrate Meta/healing

**Purpose**  
Catalog Pre-Bronze and heal operational metadata consistently.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Catalog Pre-Bronze and heal operational metadata consistently.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Catalog Pre-Bronze and heal operational metadata consistently. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.0-G — Integrate backup/restore/recovery

**Purpose**  
Backup, restore and split-commit recovery include Pre-Bronze before any production migration.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Backup, restore and split-commit recovery include Pre-Bronze before any production migration.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Backup, restore and split-commit recovery include Pre-Bronze before any production migration. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.1-A — Add Pandera adapter

**Purpose**  
One infrastructure validation adapter; application sees typed result/error.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. One infrastructure validation adapter; application sees typed result/error.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] One infrastructure validation adapter passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.1-B — Characterize Polars materialization

**Purpose**  
Benchmark LazyFrame/DataFrame validation and freeze acceptable boundary.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Benchmark LazyFrame/DataFrame validation and freeze acceptable boundary.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Benchmark LazyFrame/DataFrame validation and freeze acceptable boundary. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.1-C — Compile source validation schema

**Purpose**  
SourceDatasetConfig → required source fields/types/nullability/declared uniqueness.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. SourceDatasetConfig → required source fields/types/nullability/declared uniqueness.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] SourceDatasetConfig → required source fields/types/nullability/declared uniqueness. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.1-D — Define first canonical Bronze Pandera contract

**Purpose**  
PFETL-owned schema for selected first migration dataset.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. PFETL-owned schema for selected first migration dataset.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] PFETL-owned schema for selected first migration dataset. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.1-E — Validation error translation

**Purpose**  
Bounded examples + remediation + source/dataset/contract context.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Bounded examples + remediation + source/dataset/contract context.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Bounded examples + remediation + source/dataset/contract context. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.1-F — Validation observability

**Purpose**  
Add semantic source/Bronze validation events using existing emitter.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Add semantic source/Bronze validation events using existing emitter.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Add semantic source/Bronze validation events using existing emitter. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-A — First dataset source-plan discovery

**Purpose**  
Resolve one low-risk current dataset from SourceConfiguration to physical artifact.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Resolve one low-risk current dataset from SourceConfiguration to physical artifact.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Resolve one low-risk current dataset from SourceConfiguration to physical artifact. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-B — Raw sync with resolved policy

**Purpose**  
Control Plane sync uses SourceId/DatasetId/policy for that dataset.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Control Plane sync uses SourceId/DatasetId/policy for that dataset.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Control Plane sync uses SourceId/DatasetId/policy for that dataset. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-C — Generic provider extraction

**Purpose**  
Provider + selector returns source-shaped frame.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Provider + selector returns source-shaped frame.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Provider + selector returns source-shaped frame. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-D — Source validation and Pre-Bronze write

**Purpose**  
Validate and persist source shape.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Validate and persist source shape.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Validate and persist source shape. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-E — Normalize + identity + Bronze validation

**Purpose**  
Compile mapping, apply identity only if required, validate canonical Bronze.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Compile mapping, apply identity only if required, validate canonical Bronze.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Compile mapping, apply identity only if required, validate canonical Bronze. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-F — Canonical Bronze write and downstream equivalence

**Purpose**  
Feed existing downstream transformer; compare exact output.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Feed existing downstream transformer; compare exact output.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Feed existing downstream transformer passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-G — Rename/change/recovery proof

**Purpose**  
Exercise changed artifact, rename and rollback/replay for migrated dataset.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Exercise changed artifact, rename and rollback/replay for migrated dataset.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Exercise changed artifact, rename and rollback/replay for migrated dataset. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.2-H — Delete old path for first dataset

**Purpose**  
No permanent dual runtime for migrated dataset.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. No permanent dual runtime for migrated dataset.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] No permanent dual runtime for migrated dataset. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-A — Define typed DatasetCollection

**Purpose**  
Mapping[DatasetId, Polars frame] behind require/get/contains APIs; mappings metadata separate.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Mapping[DatasetId, Polars frame] behind require/get/contains APIs; mappings metadata separate.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Mapping[DatasetId, Polars frame] behind require/get/contains APIs passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-B — ExtractionResult adapter

**Purpose**  
Convert current ExtractionResult to DatasetCollection; no consumer migration.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Convert current ExtractionResult to DatasetCollection; no consumer migration.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Convert current ExtractionResult to DatasetCollection passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-C — Bronze full-state DatasetCollection

**Purpose**  
`BronzeLayer.get_full_dataset` produces collection alongside old result.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. `BronzeLayer.get_full_dataset` produces collection alongside old result.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] `BronzeLayer.get_full_dataset` produces collection alongside old result. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-D — Migrate Transformer consumers

**Purpose**  
Use DatasetId collection for dimensions/facts.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Use DatasetId collection for dimensions/facts.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Use DatasetId collection for dimensions/facts. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-E — Migrate investment asset strategies

**Purpose**  
Strategies use DatasetCollection.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Strategies use DatasetCollection.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Strategies use DatasetCollection. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-F — Migrate PipelineExecutor

**Purpose**  
Execution no longer depends on fixed ExtractionResult fields.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Execution no longer depends on fixed ExtractionResult fields.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Execution no longer depends on fixed ExtractionResult fields. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 9.9.3-G — Migrate coordinator and delete ExtractionResult

**Purpose**  
Delete only after repository-wide zero production references.

**Current implementation anchors**
- `application/pipeline/lifecycle.py`
- `infrastructure/warehouse/bronze.py`
- `application/ingestion/coordinator.py`
- `contracts/extraction.py`

**Exact state required after this phase**  
The named Pre-Bronze/validation/transport responsibility is fully implemented while the rest of the pipeline remains green.

**Implementation sequence**
1. Delete only after repository-wide zero production references.
2. Add focused persistence/validation/type tests.
3. Where runtime changes, run one real-data smoke and compare affected downstream outputs.

**Files / symbols expected to change**
- `infrastructure/warehouse/pre_bronze.py (when applicable)`
- `infrastructure/validation/pandera_adapter.py (when applicable)`
- `application/ingestion/*`
- `contracts/extraction.py / dataset_collection.py`
- `tests`

**Temporary coexistence / compatibility state**  
Expand/migrate adapters remain only until the named deletion phase.

**Tests and assertions**
- [ ] Delete only after repository-wide zero production references. passes.
- [ ] DuckDB rollback remains correct for persistence phases.
- [ ] No protected financial identity changes.

**Observability impact**  
Add source/dataset/validation semantic events only in the phases that introduce those runtime actions.

**Performance gate**  
Benchmark Pandera/materialization phases; otherwise compare affected real-data runtime if on hot path.

**Old-path deletion condition**  
Only the explicitly migrated old path is deleted after equivalence/recovery tests.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v10.0.0 — Complete Generalized Evidence Cutover

Each dataset migration below repeats the proven vertical template: source plan → Raw sync → provider extraction → source validation → Pre-Bronze → normalize → identity if required → Bronze validation → Bronze write → downstream equivalence → recovery/rename test → old path deletion. One dataset or tightly identical family per daily phase.


## 10.0-zcategory — Migrate `zcategory`

**Purpose**  
Move current `sqlite_source` → `bronze.r_SQLite_ZCategory` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[zcategory]`
- `ExtractionResult.zcategory`
- `bronze.r_SQLite_ZCategory`

**Exact state required after this phase**  
`zcategory` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `zcategory` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_SQLite_ZCategory`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `sqlite_source` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_SQLite_ZCategory` values match v9.5.3 semantics.
- [ ] Old `sqlite_source` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-assetgroup — Migrate `assetgroup`

**Purpose**  
Move current `sqlite_source` → `bronze.r_SQLite_AssetGroup` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[assetgroup]`
- `ExtractionResult.assetgroup`
- `bronze.r_SQLite_AssetGroup`

**Exact state required after this phase**  
`assetgroup` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `assetgroup` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_SQLite_AssetGroup`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `sqlite_source` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_SQLite_AssetGroup` values match v9.5.3 semantics.
- [ ] Old `sqlite_source` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-assets — Migrate `assets`

**Purpose**  
Move current `sqlite_source` → `bronze.r_SQLite_Assets` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[assets]`
- `ExtractionResult.assets`
- `bronze.r_SQLite_Assets`

**Exact state required after this phase**  
`assets` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `assets` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_SQLite_Assets`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `sqlite_source` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_SQLite_Assets` values match v9.5.3 semantics.
- [ ] Old `sqlite_source` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-currency — Migrate `currency`

**Purpose**  
Move current `sqlite_source` → `bronze.r_SQLite_Currency` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[currency]`
- `ExtractionResult.currency`
- `bronze.r_SQLite_Currency`

**Exact state required after this phase**  
`currency` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `currency` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_SQLite_Currency`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `sqlite_source` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_SQLite_Currency` values match v9.5.3 semantics.
- [ ] Old `sqlite_source` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-inoutcome — Migrate `inoutcome`

**Purpose**  
Move current `sqlite_source` → `bronze.r_SQLite_InOutcome` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[inoutcome]`
- `ExtractionResult.inoutcome`
- `bronze.r_SQLite_InOutcome`

**Exact state required after this phase**  
`inoutcome` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `inoutcome` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_SQLite_InOutcome`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `sqlite_source` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_SQLite_InOutcome` values match v9.5.3 semantics.
- [ ] Old `sqlite_source` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-stg_mf_isin_mapping — Migrate `stg_mf_isin_mapping`

**Purpose**  
Move current `mf_isin` → `bronze.r_MF_ISIN_Mapping` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[stg_mf_isin_mapping]`
- `ExtractionResult.stg_mf_isin_mapping`
- `bronze.r_MF_ISIN_Mapping`

**Exact state required after this phase**  
`stg_mf_isin_mapping` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `stg_mf_isin_mapping` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_MF_ISIN_Mapping`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `mf_isin` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_MF_ISIN_Mapping` values match v9.5.3 semantics.
- [ ] Old `mf_isin` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-stg_benchmark_mapping — Migrate `stg_benchmark_mapping`

**Purpose**  
Move current `benchmark_mapping` → `bronze.r_Benchmark_Mapping` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[stg_benchmark_mapping]`
- `ExtractionResult.stg_benchmark_mapping`
- `bronze.r_Benchmark_Mapping`

**Exact state required after this phase**  
`stg_benchmark_mapping` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `stg_benchmark_mapping` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Benchmark_Mapping`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `benchmark_mapping` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Benchmark_Mapping` values match v9.5.3 semantics.
- [ ] Old `benchmark_mapping` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-raw_opening_balances — Migrate `raw_opening_balances`

**Purpose**  
Move current `opening_balances` → `bronze.r_Opening_Balances` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[raw_opening_balances]`
- `ExtractionResult.raw_opening_balances`
- `bronze.r_Opening_Balances`

**Exact state required after this phase**  
`raw_opening_balances` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `raw_opening_balances` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Opening_Balances`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `opening_balances` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Opening_Balances` values match v9.5.3 semantics.
- [ ] Old `opening_balances` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-raw_benchmark_master — Migrate `raw_benchmark_master`

**Purpose**  
Move current `benchmark_master` → `bronze.r_Benchmark_Master` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[raw_benchmark_master]`
- `ExtractionResult.raw_benchmark_master`
- `bronze.r_Benchmark_Master`

**Exact state required after this phase**  
`raw_benchmark_master` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `raw_benchmark_master` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Benchmark_Master`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `benchmark_master` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Benchmark_Master` values match v9.5.3 semantics.
- [ ] Old `benchmark_master` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-raw_macro_parameters — Migrate `raw_macro_parameters`

**Purpose**  
Move current `macro_parameters` → `bronze.r_Macro_Parameters` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[raw_macro_parameters]`
- `ExtractionResult.raw_macro_parameters`
- `bronze.r_Macro_Parameters`

**Exact state required after this phase**  
`raw_macro_parameters` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `raw_macro_parameters` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Macro_Parameters`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `macro_parameters` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Macro_Parameters` values match v9.5.3 semantics.
- [ ] Old `macro_parameters` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-CFG — Retire `column_master` as a Bronze data stream

**Purpose**  
Move its OLD_COLUMN→NEW_COLUMN semantics into SourceConfiguration mapping and remove special CSV ingestion only after Shan mapping equivalence.

**Current implementation anchors**
- `application/ingestion/coordinator.py::_extract_config_tables`
- `domain/household/transforms/common.py::get_column_mapping`
- `bronze.r_Column_Master`

**Exact state required after this phase**  
Shan source configuration contains equivalent mappings; Transformer no longer receives `mappings` from ExtractionResult/DatasetCollection; r_Column_Master is removed from active Bronze contracts.

**Implementation sequence**
1. Encode every current column-master mapping in Shan configuration.
2. Compile mapping plans and compare dictionaries/normalized outputs.
3. Migrate household transform inputs to compiled plans/canonical Bronze.
4. Remove coordinator column-master extraction.
5. Remove Bronze contract/table after zero runtime consumers.

**Files / symbols expected to change**
- `source configuration fixture`
- `coordinator.py`
- `household transforms`
- `Bronze registry/schema`
- `tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] All current household mapped columns produce identical canonical values.
- [ ] No production reference to COLUMN_MASTER_PATH/get_column_mapping runtime path.
- [ ] Shan financial outputs unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-mf_market_data_raw — Migrate `mf_market_data_raw`

**Purpose**  
Move current `mf_holdings` → `bronze.r_MF_Market_Data` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[mf_market_data_raw]`
- `ExtractionResult.mf_market_data_raw`
- `bronze.r_MF_Market_Data`

**Exact state required after this phase**  
`mf_market_data_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `mf_market_data_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_MF_Market_Data`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `mf_holdings` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_MF_Market_Data` values match v9.5.3 semantics.
- [ ] Old `mf_holdings` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-us_stock_transactions_raw — Migrate `us_stock_transactions_raw`

**Purpose**  
Move current `us_stock_transactions` → `bronze.r_US_Stock_Transactions` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[us_stock_transactions_raw]`
- `ExtractionResult.us_stock_transactions_raw`
- `bronze.r_US_Stock_Transactions`

**Exact state required after this phase**  
`us_stock_transactions_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `us_stock_transactions_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_US_Stock_Transactions`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `us_stock_transactions` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_US_Stock_Transactions` values match v9.5.3 semantics.
- [ ] Old `us_stock_transactions` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-currency_mapping_raw — Migrate `currency_mapping_raw`

**Purpose**  
Move current `currency_mapping` → `bronze.r_Currency_Mapping` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[currency_mapping_raw]`
- `ExtractionResult.currency_mapping_raw`
- `bronze.r_Currency_Mapping`

**Exact state required after this phase**  
`currency_mapping_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its FULL_REPLACE change policy.
3. Extract source-shaped `currency_mapping_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Currency_Mapping`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `currency_mapping` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Currency_Mapping` values match v9.5.3 semantics.
- [ ] Old `currency_mapping` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-currency_fx_raw — Migrate `currency_fx_raw`

**Purpose**  
Move current `currency_history` → `bronze.r_Currency_FX_Data` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[currency_fx_raw]`
- `ExtractionResult.currency_fx_raw`
- `bronze.r_Currency_FX_Data`

**Exact state required after this phase**  
`currency_fx_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `currency_fx_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Currency_FX_Data`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `currency_history` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Currency_FX_Data` values match v9.5.3 semantics.
- [ ] Old `currency_history` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-mf_transactions_raw — Migrate `mf_transactions_raw`

**Purpose**  
Move current `mf_orders` → `bronze.r_MF_Transactions` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[mf_transactions_raw]`
- `ExtractionResult.mf_transactions_raw`
- `bronze.r_MF_Transactions`

**Exact state required after this phase**  
`mf_transactions_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `mf_transactions_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_MF_Transactions`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `mf_orders` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_MF_Transactions` values match v9.5.3 semantics.
- [ ] Old `mf_orders` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-stock_market_data_raw — Migrate `stock_market_data_raw`

**Purpose**  
Move current `stock_pl` → `bronze.r_Stock_Market_Data` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[stock_market_data_raw]`
- `ExtractionResult.stock_market_data_raw`
- `bronze.r_Stock_Market_Data`

**Exact state required after this phase**  
`stock_market_data_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `stock_market_data_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Stock_Market_Data`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `stock_pl` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Stock_Market_Data` values match v9.5.3 semantics.
- [ ] Old `stock_pl` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-stock_transactions_raw — Migrate `stock_transactions_raw`

**Purpose**  
Move current `stock_orders` → `bronze.r_Stock_Transactions` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[stock_transactions_raw]`
- `ExtractionResult.stock_transactions_raw`
- `bronze.r_Stock_Transactions`

**Exact state required after this phase**  
`stock_transactions_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `stock_transactions_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Stock_Transactions`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `stock_orders` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Stock_Transactions` values match v9.5.3 semantics.
- [ ] Old `stock_orders` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-benchmark_history_raw — Migrate `benchmark_history_raw`

**Purpose**  
Move current `benchmark_history` → `bronze.r_Benchmark_Data` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[benchmark_history_raw]`
- `ExtractionResult.benchmark_history_raw`
- `bronze.r_Benchmark_Data`

**Exact state required after this phase**  
`benchmark_history_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `benchmark_history_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_Benchmark_Data`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `benchmark_history` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_Benchmark_Data` values match v9.5.3 semantics.
- [ ] Old `benchmark_history` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-us_stock_market_data_raw — Migrate `us_stock_market_data_raw`

**Purpose**  
Move current `us_stock_market` → `bronze.r_US_Stock_Prices` stream completely onto the generalized evidence path.

**Current implementation anchors**
- `BRONZE_CONTRACT_REGISTRY[us_stock_market_data_raw]`
- `ExtractionResult.us_stock_market_data_raw`
- `bronze.r_US_Stock_Prices`

**Exact state required after this phase**  
`us_stock_market_data_raw` is supplied through SourcePlan/DatasetId and canonical Bronze; its fixed category/extraction-attribute path is deleted.

**Implementation sequence**
1. Bind the current source to its DatasetId and typed selector.
2. Resolve its INCREMENTAL change policy.
3. Extract source-shaped `us_stock_market_data_raw` through generic provider interface.
4. Validate and persist Pre-Bronze.
5. Apply dataset-specific mapping/normalization.
6. Apply Bronze identity policy (preserve current later-layer identity for investment evidence).
7. Validate and write canonical `bronze.r_US_Stock_Prices`.
8. Run its exact downstream transformer/engine equivalence test.
9. Exercise changed/rename/recovery behavior as applicable.
10. Delete fixed `us_stock_market` routing for this dataset only.

**Files / symbols expected to change**
- `source configuration`
- `source planner/provider registry`
- `Pre-Bronze/Bronze contracts`
- `coordinator/extractor path being retired`
- `dataset-specific tests`

**Temporary coexistence / compatibility state**  
Other datasets may still use old topology until their own migration phase; this dataset must not.

**Tests and assertions**
- [ ] Canonical `bronze.r_US_Stock_Prices` values match v9.5.3 semantics.
- [ ] Old `us_stock_market` fixed path has zero production responsibility for this dataset.
- [ ] Protected downstream IDs unchanged where applicable.
- [ ] Control Plane sync state remains truthful.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Run focused real-data timing for this dataset; full benchmark at v10 certification.

**Old-path deletion condition**  
Delete only this dataset's fixed category/extraction path after all assertions pass.

**Explicit non-goals**
- Do not migrate unrelated datasets in the same commit.
- Do not change financial formulas.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-Z1 — Remove fixed statement-folder discovery

**Purpose**  
Delete folder-name classification after every statement dataset is configuration-driven.

**Current implementation anchors**
- `infrastructure/providers/files/locator.py`
- `Settings.STATEMENTS_FOLDER`

**Exact state required after this phase**  
Application discovery is SourcePlan-driven; folder-name conventions are no longer required.

**Implementation sequence**
1. Verify every current statement dataset migrated.
2. Replace remaining caller with source-plan discovery.
3. Delete `_match_category`/required-category logic if unused.
4. Remove STATEMENTS_FOLDER from core runtime Settings if no remaining operational use.

**Files / symbols expected to change**
- `locator.py`
- `settings.py`
- `pipeline execution`
- `tests`

**Temporary coexistence / compatibility state**  
No legacy mode.

**Tests and assertions**
- [ ] Zero production references to fixed folder names.
- [ ] Shan configuration still discovers all evidence.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Delete locator category implementation and obsolete Settings field.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-Z2 — Remove Bronze dynamic source-schema evolution

**Purpose**  
Make Bronze strictly canonical now that Pre-Bronze owns source shape.

**Current implementation anchors**
- `infrastructure/warehouse/bronze.py schema evolution methods`

**Exact state required after this phase**  
Unexpected source fields can exist in Pre-Bronze but cannot mutate canonical Bronze DDL.

**Implementation sequence**
1. Remove/disable Bronze add-column evolution for canonical tables.
2. Fail Bronze admission on unmapped/unexpected canonical-contract violations.
3. Add source-drift fixture proving Pre-Bronze captures source shape while Bronze remains stable.

**Files / symbols expected to change**
- `bronze.py`
- `Bronze validation`
- `tests`

**Temporary coexistence / compatibility state**  
All datasets already migrated through Pre-Bronze.

**Tests and assertions**
- [ ] Bronze DDL does not change when source adds unrelated column.
- [ ] Validation/remediation identifies unmapped drift.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-Z3 — Replace Bronze `__file_name__` operational identity

**Purpose**  
Finish provenance migration for changed-file delete, rename and healing.

**Current implementation anchors**
- `infrastructure/warehouse/bronze.py`
- `infrastructure/warehouse/meta/healing.py`

**Exact state required after this phase**  
Artifact/source provenance key, not filename text, drives operational row ownership.

**Implementation sequence**
1. Dual-write artifact provenance key if not already present.
2. Migrate changed-artifact delete filter.
3. Migrate rename identity swap.
4. Migrate Meta healing.
5. Run rename/change/recovery tests.
6. Remove operational dependence on `__file_name__`.

**Files / symbols expected to change**
- `bronze.py`
- `meta/healing.py`
- `Pre-Bronze/Bronze schema`
- `tests`

**Temporary coexistence / compatibility state**  
Filename may remain descriptive provenance only if useful.

**Tests and assertions**
- [ ] Changed-file replacement identical.
- [ ] Rename migration identical.
- [ ] Healing identical.
- [ ] Zero operational identity decisions use filename.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.0-Z4 — v10.0.0 certification

**Purpose**  
Certify the generalized evidence architecture as authoritative.

**Current implementation anchors**
- `entire pipeline`

**Exact state required after this phase**  
No current external dataset requires fixed source topology; Raw→Pre-Bronze→Bronze is authoritative.

**Implementation sequence**
1. Run full quality gate.
2. Run Shan cached/full pipeline.
3. Compare all Silver/Gold values to oracle.
4. Compare protected IDs.
5. Exercise backup/restore and split-commit recovery.
6. Review JSONL lineage.
7. Run external no-UID household fixture.
8. Record performance delta and resolve material regressions.

**Files / symbols expected to change**
- `tests/quality gate`
- `real-data certification artifacts`

**Temporary coexistence / compatibility state**  
No legacy ingestion mode.

**Tests and assertions**
- [ ] All financial comparisons pass.
- [ ] All current sources represented by configuration.
- [ ] No fixed ExtractionResult/source-category orchestration remains.
- [ ] Performance approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Mandatory full cached and cold benchmark.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v10.1.x — Full Capability Composition

## 10.1.0-A — Freeze Household capability contract

**Purpose**  
Define exact required/optional inputs and outputs for Household.

**Current implementation anchors**
- `TransformationDAG household dimensions/facts`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for Household names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: household canonical Bronze.
2. Inventory exact outputs: household Silver + household Gold/wealth inputs.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] Household descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.0-B — Make Household orchestration plan-driven

**Purpose**  
Execute Household only when present in ExecutionPlan.

**Current implementation anchors**
- `TransformationDAG household dimensions/facts`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes Household from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing Household orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled Household output equals current behavior.
- [ ] Disabled Household performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.0-C — Make Household publication/completeness plan-aware

**Purpose**  
Align active contracts with Household enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through Household are required/published.

**Implementation sequence**
1. Add/remove Household contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled Household contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.0-D — Household enabled/disabled real-data certification

**Purpose**  
Prove Household composition on representative configuration.

**Current implementation anchors**
- `TransformationDAG household dimensions/facts`

**Exact state required after this phase**  
Household is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare Household outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.1-A — Freeze Investment accounting capability contract

**Purpose**  
Define exact required/optional inputs and outputs for Investment accounting.

**Current implementation anchors**
- `MF/Indian/US transforms + Quant accounting`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for Investment accounting names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: investment evidence + investment master.
2. Inventory exact outputs: purchase/sale/lots/realized/reconciliation + investment Gold.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] Investment accounting descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.1-B — Make Investment accounting orchestration plan-driven

**Purpose**  
Execute Investment accounting only when present in ExecutionPlan.

**Current implementation anchors**
- `MF/Indian/US transforms + Quant accounting`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes Investment accounting from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing Investment accounting orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled Investment accounting output equals current behavior.
- [ ] Disabled Investment accounting performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.1-C — Make Investment accounting publication/completeness plan-aware

**Purpose**  
Align active contracts with Investment accounting enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through Investment accounting are required/published.

**Implementation sequence**
1. Add/remove Investment accounting contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled Investment accounting contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.1-D — Investment accounting enabled/disabled real-data certification

**Purpose**  
Prove Investment accounting composition on representative configuration.

**Current implementation anchors**
- `MF/Indian/US transforms + Quant accounting`

**Exact state required after this phase**  
Investment accounting is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare Investment accounting outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.2-A — Freeze Benchmark enrichment capability contract

**Purpose**  
Define exact required/optional inputs and outputs for Benchmark enrichment.

**Current implementation anchors**
- `benchmark transform + Quant optional benchmark input`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for Benchmark enrichment names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: benchmark master/history.
2. Inventory exact outputs: benchmark analytics contribution.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] Benchmark enrichment descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.2-B — Make Benchmark enrichment orchestration plan-driven

**Purpose**  
Execute Benchmark enrichment only when present in ExecutionPlan.

**Current implementation anchors**
- `benchmark transform + Quant optional benchmark input`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes Benchmark enrichment from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing Benchmark enrichment orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled Benchmark enrichment output equals current behavior.
- [ ] Disabled Benchmark enrichment performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.2-C — Make Benchmark enrichment publication/completeness plan-aware

**Purpose**  
Align active contracts with Benchmark enrichment enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through Benchmark enrichment are required/published.

**Implementation sequence**
1. Add/remove Benchmark enrichment contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled Benchmark enrichment contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.2-D — Benchmark enrichment enabled/disabled real-data certification

**Purpose**  
Prove Benchmark enrichment composition on representative configuration.

**Current implementation anchors**
- `benchmark transform + Quant optional benchmark input`

**Exact state required after this phase**  
Benchmark enrichment is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare Benchmark enrichment outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.3-A — Freeze Foreign assets / FX capability contract

**Purpose**  
Define exact required/optional inputs and outputs for Foreign assets / FX.

**Current implementation anchors**
- `currency + US market sync/processors`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for Foreign assets / FX names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: foreign investment evidence + FX/US market.
2. Inventory exact outputs: foreign valuation contribution.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] Foreign assets / FX descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.3-B — Make Foreign assets / FX orchestration plan-driven

**Purpose**  
Execute Foreign assets / FX only when present in ExecutionPlan.

**Current implementation anchors**
- `currency + US market sync/processors`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes Foreign assets / FX from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing Foreign assets / FX orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled Foreign assets / FX output equals current behavior.
- [ ] Disabled Foreign assets / FX performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.3-C — Make Foreign assets / FX publication/completeness plan-aware

**Purpose**  
Align active contracts with Foreign assets / FX enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through Foreign assets / FX are required/published.

**Implementation sequence**
1. Add/remove Foreign assets / FX contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled Foreign assets / FX contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.3-D — Foreign assets / FX enabled/disabled real-data certification

**Purpose**  
Prove Foreign assets / FX composition on representative configuration.

**Current implementation anchors**
- `currency + US market sync/processors`

**Exact state required after this phase**  
Foreign assets / FX is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare Foreign assets / FX outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.4-A — Freeze Tax capability contract

**Purpose**  
Define exact required/optional inputs and outputs for Tax.

**Current implementation anchors**
- `TaxEngine`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for Tax names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: income + optional realized events + macro parameters.
2. Inventory exact outputs: Tax events + 3 Tax Gold.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] Tax descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.4-B — Make Tax orchestration plan-driven

**Purpose**  
Execute Tax only when present in ExecutionPlan.

**Current implementation anchors**
- `TaxEngine`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes Tax from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing Tax orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled Tax output equals current behavior.
- [ ] Disabled Tax performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.4-C — Make Tax publication/completeness plan-aware

**Purpose**  
Align active contracts with Tax enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through Tax are required/published.

**Implementation sequence**
1. Add/remove Tax contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled Tax contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.4-D — Tax enabled/disabled real-data certification

**Purpose**  
Prove Tax composition on representative configuration.

**Current implementation anchors**
- `TaxEngine`

**Exact state required after this phase**  
Tax is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare Tax outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.5-A — Freeze Wealth capability contract

**Purpose**  
Define exact required/optional inputs and outputs for Wealth.

**Current implementation anchors**
- `WealthPresentationEngine core models`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for Wealth names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: household state + optional investment analytics.
2. Inventory exact outputs: wealth/cashflow Gold.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] Wealth descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.5-B — Make Wealth orchestration plan-driven

**Purpose**  
Execute Wealth only when present in ExecutionPlan.

**Current implementation anchors**
- `WealthPresentationEngine core models`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes Wealth from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing Wealth orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled Wealth output equals current behavior.
- [ ] Disabled Wealth performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.5-C — Make Wealth publication/completeness plan-aware

**Purpose**  
Align active contracts with Wealth enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through Wealth are required/published.

**Implementation sequence**
1. Add/remove Wealth contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled Wealth contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.5-D — Wealth enabled/disabled real-data certification

**Purpose**  
Prove Wealth composition on representative configuration.

**Current implementation anchors**
- `WealthPresentationEngine core models`

**Exact state required after this phase**  
Wealth is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare Wealth outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.6-A — Freeze FIRE / simulation capability contract

**Purpose**  
Define exact required/optional inputs and outputs for FIRE / simulation.

**Current implementation anchors**
- `WealthRiskAnalyticsBuilder + FIRE builders`
- `DATA_CONTRACT_REGISTRY`

**Exact state required after this phase**  
CapabilityDescriptor for FIRE / simulation names required/optional datasets and produced contracts.

**Implementation sequence**
1. Inventory exact inputs: wealth/household + configured assumptions.
2. Inventory exact outputs: FIRE/risk Gold + simulation provenance.
3. Encode required capability dependencies.
4. Add graph validation tests.

**Files / symbols expected to change**
- `contracts/capabilities.py`
- `capability registry`
- `tests`

**Temporary coexistence / compatibility state**  
Full Shan plan remains enabled.

**Tests and assertions**
- [ ] FIRE / simulation descriptor resolves with full configuration.
- [ ] Missing required dependency fails planning, not mid-engine.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.6-B — Make FIRE / simulation orchestration plan-driven

**Purpose**  
Execute FIRE / simulation only when present in ExecutionPlan.

**Current implementation anchors**
- `WealthRiskAnalyticsBuilder + FIRE builders`
- `application/pipeline/execution.py`

**Exact state required after this phase**  
PipelineExecutor invokes FIRE / simulation from plan/stage ownership; no domain module reads configuration flags.

**Implementation sequence**
1. Gate the existing FIRE / simulation orchestration at application boundary using plan.
2. Preserve current call order when enabled.
3. Ensure disabled path does not construct providers/services unnecessarily.

**Files / symbols expected to change**
- `pipeline execution`
- `relevant application service`
- `tests`

**Temporary coexistence / compatibility state**  
Full plan behavior unchanged; disabled plan is now supported.

**Tests and assertions**
- [ ] Enabled FIRE / simulation output equals current behavior.
- [ ] Disabled FIRE / simulation performs no engine/provider work.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.6-C — Make FIRE / simulation publication/completeness plan-aware

**Purpose**  
Align active contracts with FIRE / simulation enablement.

**Current implementation anchors**
- `SilverLayer.load`
- `GoldLayer.load`
- `PipelineExecutor._run_analytics_phase`

**Exact state required after this phase**  
Only contracts active through FIRE / simulation are required/published.

**Implementation sequence**
1. Add/remove FIRE / simulation contracts from active sets through planner.
2. Update completeness tests.
3. Update publication tests.
4. Verify no stale tables survive full rebuild when disabled.

**Files / symbols expected to change**
- `capability planner`
- `Silver/Gold loaders`
- `tests`

**Temporary coexistence / compatibility state**  
Other capabilities remain unaffected.

**Tests and assertions**
- [ ] Disabled FIRE / simulation contracts absent.
- [ ] Unrelated contracts and values unchanged.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.1.6-D — FIRE / simulation enabled/disabled real-data certification

**Purpose**  
Prove FIRE / simulation composition on representative configuration.

**Current implementation anchors**
- `WealthRiskAnalyticsBuilder + FIRE builders`

**Exact state required after this phase**  
FIRE / simulation is independently composable according to its descriptor.

**Implementation sequence**
1. Run full Shan plan and compare FIRE / simulation outputs.
2. Run configuration with capability disabled where valid.
3. Run invalid dependency configuration and verify pre-run failure.

**Files / symbols expected to change**
- `integration fixtures`
- `real-data certification`

**Temporary coexistence / compatibility state**  
No compatibility adapter added.

**Tests and assertions**
- [ ] Full plan remains oracle-equivalent.
- [ ] Disabled/invalid behavior matches contract.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
Compare runtime to expected reduction when disabled; no regression when enabled.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v10.2.x — Plan-Aware Warehouse and Recovery

## 10.2.0-A — Active Silver DDL

**Purpose**  
Create/recreate only Silver contracts active in ExecutionPlan.

**Current implementation anchors**
- `infrastructure/warehouse/silver.py`
- `schema/silver.py`

**Exact state required after this phase**  
Create/recreate only Silver contracts active in ExecutionPlan.

**Implementation sequence**
1. Create/recreate only Silver contracts active in ExecutionPlan.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `infrastructure/warehouse/silver.py`
- `schema/silver.py`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Create/recreate only Silver contracts active in ExecutionPlan. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.0-B — Active Gold DDL

**Purpose**  
Create/recreate only Gold contracts active in ExecutionPlan.

**Current implementation anchors**
- `infrastructure/warehouse/gold.py`
- `schema/gold.py`

**Exact state required after this phase**  
Create/recreate only Gold contracts active in ExecutionPlan.

**Implementation sequence**
1. Create/recreate only Gold contracts active in ExecutionPlan.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `infrastructure/warehouse/gold.py`
- `schema/gold.py`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Create/recreate only Gold contracts active in ExecutionPlan. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.0-C — Meta/catalog active-universe semantics

**Purpose**  
Meta fingerprint/catalog records active contract universe and plan fingerprint.

**Current implementation anchors**
- `infrastructure/warehouse/meta/layer.py`

**Exact state required after this phase**  
Meta fingerprint/catalog records active contract universe and plan fingerprint.

**Implementation sequence**
1. Meta fingerprint/catalog records active contract universe and plan fingerprint.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `infrastructure/warehouse/meta/layer.py`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Meta fingerprint/catalog records active contract universe and plan fingerprint. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.0-D — Capability switch cleanup

**Purpose**  
A rerun with a capability disabled removes its previously published tables rather than leaving stale state.

**Current implementation anchors**
- `SilverLayer`
- `GoldLayer`
- `MetaLayer`

**Exact state required after this phase**  
A rerun with a capability disabled removes its previously published tables rather than leaving stale state.

**Implementation sequence**
1. A rerun with a capability disabled removes its previously published tables rather than leaving stale state.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `SilverLayer`
- `GoldLayer`
- `MetaLayer`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] A rerun with a capability disabled removes its previously published tables rather than leaving stale state. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.1-A — Bronze contract certification

**Purpose**  
Every canonical Bronze dataset has schema/type/identity/grain tests.

**Current implementation anchors**
- `Bronze contracts`
- `Pandera schemas`

**Exact state required after this phase**  
Every canonical Bronze dataset has schema/type/identity/grain tests.

**Implementation sequence**
1. Every canonical Bronze dataset has schema/type/identity/grain tests.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `Bronze contracts`
- `Pandera schemas`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Every canonical Bronze dataset has schema/type/identity/grain tests. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.1-B — Silver contract certification

**Purpose**  
Every Silver dataset has grain/identity/domain/capability tests.

**Current implementation anchors**
- `DATA_CONTRACT_REGISTRY`
- `silver schema`

**Exact state required after this phase**  
Every Silver dataset has grain/identity/domain/capability tests.

**Implementation sequence**
1. Every Silver dataset has grain/identity/domain/capability tests.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `DATA_CONTRACT_REGISTRY`
- `silver schema`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Every Silver dataset has grain/identity/domain/capability tests. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.1-C — Gold contract certification

**Purpose**  
Every Gold dataset has grain/input/capability tests.

**Current implementation anchors**
- `gold schema`
- `Gold producers`

**Exact state required after this phase**  
Every Gold dataset has grain/input/capability tests.

**Implementation sequence**
1. Every Gold dataset has grain/input/capability tests.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `gold schema`
- `Gold producers`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Every Gold dataset has grain/input/capability tests. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.2-A — Failure after Raw before Pre-Bronze

**Purpose**  
Prove rollback/replay semantics for earliest generalized stage.

**Current implementation anchors**
- `lifecycle`
- `Control Plane`
- `PreBronzeLayer`

**Exact state required after this phase**  
Prove rollback/replay semantics for earliest generalized stage.

**Implementation sequence**
1. Prove rollback/replay semantics for earliest generalized stage.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `lifecycle`
- `Control Plane`
- `PreBronzeLayer`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Prove rollback/replay semantics for earliest generalized stage. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.2-B — Failure after Pre-Bronze before Bronze

**Purpose**  
Prove DuckDB rollback + SQLite rollback truth.

**Current implementation anchors**
- `lifecycle`
- `PreBronzeLayer`
- `BronzeLayer`

**Exact state required after this phase**  
Prove DuckDB rollback + SQLite rollback truth.

**Implementation sequence**
1. Prove DuckDB rollback + SQLite rollback truth.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `lifecycle`
- `PreBronzeLayer`
- `BronzeLayer`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Prove DuckDB rollback + SQLite rollback truth. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.2-C — Failure after Bronze before analytics

**Purpose**  
Prove full run transaction rollback.

**Current implementation anchors**
- `lifecycle`
- `BronzeLayer`

**Exact state required after this phase**  
Prove full run transaction rollback.

**Implementation sequence**
1. Prove full run transaction rollback.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `lifecycle`
- `BronzeLayer`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Prove full run transaction rollback. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.2-D — Split commit after DuckDB commit

**Purpose**  
Preserve RECOVERY_REQUIRED and next-run convergence with Pre-Bronze included.

**Current implementation anchors**
- `RunLifecycleCoordinator.commit`
- `Control Plane recovery`

**Exact state required after this phase**  
Preserve RECOVERY_REQUIRED and next-run convergence with Pre-Bronze included.

**Implementation sequence**
1. Preserve RECOVERY_REQUIRED and next-run convergence with Pre-Bronze included.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `RunLifecycleCoordinator.commit`
- `Control Plane recovery`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Preserve RECOVERY_REQUIRED and next-run convergence with Pre-Bronze included. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.2-E — Mapping/config change replay

**Purpose**  
Fingerprint change is recorded and affected canonical state is rebuilt deliberately.

**Current implementation anchors**
- `config snapshots`
- `source planner`
- `warehouse`

**Exact state required after this phase**  
Fingerprint change is recorded and affected canonical state is rebuilt deliberately.

**Implementation sequence**
1. Fingerprint change is recorded and affected canonical state is rebuilt deliberately.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `config snapshots`
- `source planner`
- `warehouse`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Fingerprint change is recorded and affected canonical state is rebuilt deliberately. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.2.2-F — Identity-policy change safety

**Purpose**  
Never silently reinterpret historical Bronze IDs; require explicit rebuild/migration behavior.

**Current implementation anchors**
- `identity plan`
- `config fingerprint`
- `Control Plane`

**Exact state required after this phase**  
Never silently reinterpret historical Bronze IDs; require explicit rebuild/migration behavior.

**Implementation sequence**
1. Never silently reinterpret historical Bronze IDs; require explicit rebuild/migration behavior.
2. Add the exact focused integration test for this boundary.
3. Run Shan smoke if persistence/runtime changes.

**Files / symbols expected to change**
- `identity plan`
- `config fingerprint`
- `Control Plane`
- `tests`

**Temporary coexistence / compatibility state**  
No new parallel recovery protocol.

**Tests and assertions**
- [ ] Never silently reinterpret historical Bronze IDs; require explicit rebuild/migration behavior. verified.
- [ ] Commit state remains truthful.

**Observability impact**  
Emit existing recovery/database events with added dataset/config context where relevant.

**Performance gate**  
No dedicated performance gate unless normal run path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v10.3.x — Core External-User Usability

## 10.3.0-A — `validate-config`

**Purpose**  
Validate schema version, references, mapping, identity and capability graph without financial execution.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Validate schema version, references, mapping, identity and capability graph without financial execution.

**Implementation sequence**
1. Validate schema version, references, mapping, identity and capability graph without financial execution.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Validate schema version, references, mapping, identity and capability graph without financial execution. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.0-B — source reachability validation

**Purpose**  
Check configured files/SQLite/selectors and report source/dataset-specific remediation.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Check configured files/SQLite/selectors and report source/dataset-specific remediation.

**Implementation sequence**
1. Check configured files/SQLite/selectors and report source/dataset-specific remediation.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Check configured files/SQLite/selectors and report source/dataset-specific remediation. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.0-C — source schema preview

**Purpose**  
Display observed columns/types against declared source contract.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Display observed columns/types against declared source contract.

**Implementation sequence**
1. Display observed columns/types against declared source contract.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Display observed columns/types against declared source contract. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.0-D — mapping preview

**Purpose**  
Display source→canonical mapping and normalization plan.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Display source→canonical mapping and normalization plan.

**Implementation sequence**
1. Display source→canonical mapping and normalization plan.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Display source→canonical mapping and normalization plan. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.0-E — identity preview

**Purpose**  
Display strategy, bounded sample IDs and collision diagnostics.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Display strategy, bounded sample IDs and collision diagnostics.

**Implementation sequence**
1. Display strategy, bounded sample IDs and collision diagnostics.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Display strategy, bounded sample IDs and collision diagnostics. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.0-F — capability-plan preview

**Purpose**  
Display requested/resolved capabilities, required datasets, active Silver/Gold.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Display requested/resolved capabilities, required datasets, active Silver/Gold.

**Implementation sequence**
1. Display requested/resolved capabilities, required datasets, active Silver/Gold.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Display requested/resolved capabilities, required datasets, active Silver/Gold. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.0-G — admission dry-run

**Purpose**  
Run discovery/extraction/source validation/normalization/Bronze validation without financial publication, with no durable analytical mutation.

**Current implementation anchors**
- `presentation/cli`
- `application source/capability services`

**Exact state required after this phase**  
Run discovery/extraction/source validation/normalization/Bronze validation without financial publication, with no durable analytical mutation.

**Implementation sequence**
1. Run discovery/extraction/source validation/normalization/Bronze validation without financial publication, with no durable analytical mutation.
2. Expose through application facade/service rather than duplicating logic in CLI.
3. Add success and actionable-failure tests.

**Files / symbols expected to change**
- `presentation CLI`
- `application facade/services`
- `tests`

**Temporary coexistence / compatibility state**  
No companion application required.

**Tests and assertions**
- [ ] Run discovery/extraction/source validation/normalization/Bronze validation without financial publication, with no durable analytical mutation. works on Shan config and at least one external fixture.
- [ ] No financial tables are published by validation-only commands.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-01 — External fixture: Excel household without source IDs

**Purpose**  
Prove PFETL core handles Excel household without source IDs without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for Excel household without source IDs passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for Excel household without source IDs.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] Excel household without source IDs behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-02 — External fixture: CSV household

**Purpose**  
Prove PFETL core handles CSV household without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for CSV household passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for CSV household.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] CSV household behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-03 — External fixture: SQLite household with trusted IDs

**Purpose**  
Prove PFETL core handles SQLite household with trusted IDs without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for SQLite household with trusted IDs passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for SQLite household with trusted IDs.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] SQLite household with trusted IDs behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-04 — External fixture: household-only

**Purpose**  
Prove PFETL core handles household-only without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for household-only passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for household-only.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] household-only behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-05 — External fixture: household + domestic investments

**Purpose**  
Prove PFETL core handles household + domestic investments without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for household + domestic investments passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for household + domestic investments.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] household + domestic investments behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-06 — External fixture: household + foreign assets

**Purpose**  
Prove PFETL core handles household + foreign assets without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for household + foreign assets passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for household + foreign assets.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] household + foreign assets behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-07 — External fixture: household + Tax

**Purpose**  
Prove PFETL core handles household + Tax without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for household + Tax passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for household + Tax.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] household + Tax behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-08 — External fixture: household + FIRE

**Purpose**  
Prove PFETL core handles household + FIRE without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for household + FIRE passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for household + FIRE.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] household + FIRE behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-09 — External fixture: malformed source schema

**Purpose**  
Prove PFETL core handles malformed source schema without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for malformed source schema passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for malformed source schema.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] malformed source schema behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-10 — External fixture: bad mapping

**Purpose**  
Prove PFETL core handles bad mapping without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for bad mapping passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for bad mapping.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] bad mapping behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-11 — External fixture: identity collision

**Purpose**  
Prove PFETL core handles identity collision without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for identity collision passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for identity collision.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] identity collision behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-12 — External fixture: invalid capability dependency

**Purpose**  
Prove PFETL core handles invalid capability dependency without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for invalid capability dependency passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for invalid capability dependency.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] invalid capability dependency behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-13 — External fixture: source rename

**Purpose**  
Prove PFETL core handles source rename without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for source rename passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for source rename.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] source rename behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-14 — External fixture: changed source under content-hash policy

**Purpose**  
Prove PFETL core handles changed source under content-hash policy without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for changed source under content-hash policy passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for changed source under content-hash policy.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] changed source under content-hash policy behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.1-15 — External fixture: mapping change between runs

**Purpose**  
Prove PFETL core handles mapping change between runs without Python source modification.

**Current implementation anchors**
- `test fixtures`
- `SourceConfiguration`
- `pipeline`

**Exact state required after this phase**  
A deterministic integration fixture for mapping change between runs passes with explicit expected Control Plane and warehouse state.

**Implementation sequence**
1. Create minimal source evidence/config for mapping change between runs.
2. Define expected validation/plan/result state.
3. Run end-to-end or expected pre-run failure.
4. Assert active contract set and Control Plane status.

**Files / symbols expected to change**
- `tests/fixtures`
- `integration tests`

**Temporary coexistence / compatibility state**  
No fixture-specific production branch.

**Tests and assertions**
- [ ] mapping change between runs behavior matches specification.
- [ ] No production code contains fixture/user-specific special case.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v10.3.2 — Performance Hardening

## 10.3.2-A — Measure Pre-Bronze overhead

**Purpose**  
Benchmark Raw→Pre-Bronze persistence on Shan workload.

**Current implementation anchors**
- `performance benchmark harness`
- `pipeline`

**Exact state required after this phase**  
Benchmark Raw→Pre-Bronze persistence on Shan workload.

**Implementation sequence**
1. Benchmark Raw→Pre-Bronze persistence on Shan workload.
2. Record before/after measurement.
3. Do not weaken validation to win benchmark.

**Files / symbols expected to change**
- `benchmarks/tests`
- `affected hot path`

**Temporary coexistence / compatibility state**  
No semantic changes.

**Tests and assertions**
- [ ] Benchmark Raw→Pre-Bronze persistence on Shan workload. recorded/approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
This phase is itself the performance gate.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.2-B — Measure Pandera overhead

**Purpose**  
Benchmark source + Bronze validation materialization/cost.

**Current implementation anchors**
- `performance benchmark harness`
- `pipeline`

**Exact state required after this phase**  
Benchmark source + Bronze validation materialization/cost.

**Implementation sequence**
1. Benchmark source + Bronze validation materialization/cost.
2. Record before/after measurement.
3. Do not weaken validation to win benchmark.

**Files / symbols expected to change**
- `benchmarks/tests`
- `affected hot path`

**Temporary coexistence / compatibility state**  
No semantic changes.

**Tests and assertions**
- [ ] Benchmark source + Bronze validation materialization/cost. recorded/approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
This phase is itself the performance gate.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.2-C — Measure normalization/identity overhead

**Purpose**  
Benchmark mapping and derived-ID stages.

**Current implementation anchors**
- `performance benchmark harness`
- `pipeline`

**Exact state required after this phase**  
Benchmark mapping and derived-ID stages.

**Implementation sequence**
1. Benchmark mapping and derived-ID stages.
2. Record before/after measurement.
3. Do not weaken validation to win benchmark.

**Files / symbols expected to change**
- `benchmarks/tests`
- `affected hot path`

**Temporary coexistence / compatibility state**  
No semantic changes.

**Tests and assertions**
- [ ] Benchmark mapping and derived-ID stages. recorded/approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
This phase is itself the performance gate.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.2-D — Optimize measured bottlenecks only

**Purpose**  
Apply changes only where profiling identifies material regression; preserve contracts.

**Current implementation anchors**
- `performance benchmark harness`
- `pipeline`

**Exact state required after this phase**  
Apply changes only where profiling identifies material regression; preserve contracts.

**Implementation sequence**
1. Apply changes only where profiling identifies material regression; preserve contracts.
2. Record before/after measurement.
3. Do not weaken validation to win benchmark.

**Files / symbols expected to change**
- `benchmarks/tests`
- `affected hot path`

**Temporary coexistence / compatibility state**  
No semantic changes.

**Tests and assertions**
- [ ] Apply changes only where profiling identifies material regression; preserve contracts. recorded/approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
This phase is itself the performance gate.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.2-E — Certify cached/full Shan runtime

**Purpose**  
Approve final generalized runtime budget.

**Current implementation anchors**
- `performance benchmark harness`
- `pipeline`

**Exact state required after this phase**  
Approve final generalized runtime budget.

**Implementation sequence**
1. Approve final generalized runtime budget.
2. Record before/after measurement.
3. Do not weaken validation to win benchmark.

**Files / symbols expected to change**
- `benchmarks/tests`
- `affected hot path`

**Temporary coexistence / compatibility state**  
No semantic changes.

**Tests and assertions**
- [ ] Approve final generalized runtime budget. recorded/approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
This phase is itself the performance gate.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.3.2-F — Certify representative external fixtures

**Purpose**  
Ensure generalized flexibility has no pathological scaling behavior.

**Current implementation anchors**
- `performance benchmark harness`
- `pipeline`

**Exact state required after this phase**  
Ensure generalized flexibility has no pathological scaling behavior.

**Implementation sequence**
1. Ensure generalized flexibility has no pathological scaling behavior.
2. Record before/after measurement.
3. Do not weaken validation to win benchmark.

**Files / symbols expected to change**
- `benchmarks/tests`
- `affected hot path`

**Temporary coexistence / compatibility state**  
No semantic changes.

**Tests and assertions**
- [ ] Ensure generalized flexibility has no pathological scaling behavior. recorded/approved.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
This phase is itself the performance gate.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.
# v10.4.x — Public Configuration Freeze and Core Acceptance

## 10.4.0-A — Review/freeze source configuration field names

**Purpose**  
Treat SourceConfiguration as a public PFETL contract; remove migration-era names before freeze.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Treat SourceConfiguration as a public PFETL contract; remove migration-era names before freeze.

**Implementation sequence**
1. Treat SourceConfiguration as a public PFETL contract; remove migration-era names before freeze.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Treat SourceConfiguration as a public PFETL contract; remove migration-era names before freeze. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.0-B — Review/freeze DatasetIds

**Purpose**  
Ensure semantic IDs are source/provider independent.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Ensure semantic IDs are source/provider independent.

**Implementation sequence**
1. Ensure semantic IDs are source/provider independent.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Ensure semantic IDs are source/provider independent. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.0-C — Review/freeze identity/change-policy schema

**Purpose**  
Ensure policies express semantics without provider coupling.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Ensure policies express semantics without provider coupling.

**Implementation sequence**
1. Ensure policies express semantics without provider coupling.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Ensure policies express semantics without provider coupling. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.0-D — Review/freeze CapabilityIds

**Purpose**  
Ensure IDs correspond to real financial execution ownership.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Ensure IDs correspond to real financial execution ownership.

**Implementation sequence**
1. Ensure IDs correspond to real financial execution ownership.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Ensure IDs correspond to real financial execution ownership. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.0-E — Add schema-version migration framework

**Purpose**  
Future config versions fail clearly or migrate through explicit versioned transformations.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Future config versions fail clearly or migrate through explicit versioned transformations.

**Implementation sequence**
1. Future config versions fail clearly or migrate through explicit versioned transformations.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Future config versions fail clearly or migrate through explicit versioned transformations. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.0-F — Export machine-readable configuration schema

**Purpose**  
PFETL package/CLI can emit schema for humans/tools; companion applications remain out of scope.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
PFETL package/CLI can emit schema for humans/tools; companion applications remain out of scope.

**Implementation sequence**
1. PFETL package/CLI can emit schema for humans/tools; companion applications remain out of scope.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] PFETL package/CLI can emit schema for humans/tools; companion applications remain out of scope. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.1-A — Clean install acceptance

**Purpose**  
Install in clean environment and run CLI/config validation.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Install in clean environment and run CLI/config validation.

**Implementation sequence**
1. Install in clean environment and run CLI/config validation.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Install in clean environment and run CLI/config validation. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.1-B — New-user household run

**Purpose**  
Use only documented config + external fixture; no code edits.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Use only documented config + external fixture; no code edits.

**Implementation sequence**
1. Use only documented config + external fixture; no code edits.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Use only documented config + external fixture; no code edits. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.1-C — Add investments and incremental rerun

**Purpose**  
Modify config/evidence and rerun correctly.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Modify config/evidence and rerun correctly.

**Implementation sequence**
1. Modify config/evidence and rerun correctly.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Modify config/evidence and rerun correctly. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.1-D — Failure/remediation acceptance

**Purpose**  
Trigger source/Bronze/capability failures and verify actionable diagnostics.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Trigger source/Bronze/capability failures and verify actionable diagnostics.

**Implementation sequence**
1. Trigger source/Bronze/capability failures and verify actionable diagnostics.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Trigger source/Bronze/capability failures and verify actionable diagnostics. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

## 10.4.1-E — Backup/restore/incremental acceptance

**Purpose**  
Prove operational lifecycle for external-style configuration.

**Current implementation anchors**
- `public config contracts`
- `CLI/application facade`
- `pipeline`

**Exact state required after this phase**  
Prove operational lifecycle for external-style configuration.

**Implementation sequence**
1. Prove operational lifecycle for external-style configuration.
2. Add compatibility/deprecation test where contract is frozen.
3. Run relevant external fixture.

**Files / symbols expected to change**
- `config/contracts`
- `CLI/application`
- `tests`

**Temporary coexistence / compatibility state**  
No companion app.

**Tests and assertions**
- [ ] Prove operational lifecycle for external-style configuration. complete.
- [ ] No source-code modification required for acceptance flow.

**Observability impact**  
No new event required unless stated below.

**Performance gate**  
No dedicated benchmark beyond regression unless runtime path changes.

**Old-path deletion condition**  
Nothing in this phase.

**Explicit non-goals**
- Do not pull work from the next phase.

**Commit-ready exit**  
All assertions above pass; repository compiles; affected static checks are green; no known half-migrated ownership remains.

# v11.0.0 — Conditional Major Boundary Only

Do **not** create v11 merely to finish the document. v11.0.0 is justified only if v10.x intentionally carried temporary public compatibility that must be removed through a breaking PFETL-core contract. Examples: a deprecated configuration schema, deprecated physical Silver/Gold names, or migration-only aliases.

If no such breaking boundary remains after v10.4.x acceptance, the Grand Refactor ends in v10.x.

If v11 is required, its phases are strictly:

1. provide/verify configuration migration command;
2. remove explicitly deprecated v10 configuration fields;
3. remove explicitly deprecated analytical aliases/physical names;
4. migrate every external fixture;
5. rerun complete financial/recovery/performance certification.

No new architecture is introduced in v11.

# PART V — RELEASE GATES

## Every phase
- compile/import smoke;
- focused tests;
- architecture tests for changed boundary;
- formatter/linter for touched code;
- no knowingly broken compatibility.

## Every patch release
- full static typing;
- affected subsystem suite;
- documentation/code-quality auditor.

## Every minor release
- complete quality gate;
- Shan real-data run if runtime path changed;
- exact financial regression where semantics unchanged;
- JSONL lineage review;
- runtime comparison.

## Persistence/schema changes
- rollback;
- backup/restore;
- recovery/replay;
- Meta/catalog consistency.

# PART VI — STOP CONDITIONS

Stop and amend this specification if implementation requires any of the following:

- arbitrary user Python/eval to map a supported source;
- user-defined canonical Bronze/Silver/Gold schema;
- Pre-Bronze calculating financial meaning;
- Bronze identity based on row order/randomness;
- source category/folder controlling financial semantics;
- provider symbol becoming canonical identity without explicit financial justification;
- capability booleans scattered into domain modules;
- a migration changing a financial formula merely to simplify schema work;
- a multi-day knowingly broken branch because a prerequisite phase was omitted.

# PART VII — DAILY PHASE RECORD

For each phase record:

```text
Phase:
Version:
Ledger rows closed:
Files changed:
Contracts changed:
Schema changed: yes/no
Financial formulas changed: MUST BE NO unless separately approved
Compatibility path remaining:
Old path deletion condition:
Focused tests:
Architecture tests:
Real-data verification:
Performance verification:
Observability impact:
Exit assertions green: yes/no
Commit:
```

# PART VIII — FINAL PFETL CORE ACCEPTANCE

The Grand Refactor is complete when a person whose source topology differs from Shan's can, using only PFETL itself:

1. install PFETL;
2. author a versioned configuration;
3. configure supported CSV/Excel/SQLite sources;
4. select tables/sheets/files;
5. map and normalize source fields;
6. choose allowed change-detection policies;
7. supply identity strategy where the canonical Bronze contract requires it;
8. select supported capabilities;
9. validate configuration and source reachability;
10. preview mapping, identity and execution plan;
11. run Raw → Pre-Bronze → Bronze;
12. pass PFETL-owned canonical validation;
13. execute only required financial engines;
14. persist only active Silver/Gold contracts;
15. rerun incrementally;
16. backup/restore/recover;
17. reconstruct failures through observability lineage;
18. do all of this without modifying PFETL Python source.

> **Users configure their evidence and capabilities. PFETL owns the financial meaning.**
