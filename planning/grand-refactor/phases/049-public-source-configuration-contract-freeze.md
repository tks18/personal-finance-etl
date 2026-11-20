# Phase 049 - Public Source-Configuration Contract Freeze

**Target release:** v10.4.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 048  
**Next:** Phase 050  
**Risk:** High

## 1. Outcome

Freeze version 1 of PFETL's public source-configuration contract after reviewing every field against the external certification experience. Publish a machine-readable schema, explicit compatibility/deprecation rules, and stable identifier vocabularies needed by future companion tools.

Publish the finalized, frozen canonical column catalogs across all datasets, certifying that external users configure only the clean, slimmed-down canonical fields established in Phases 046–047 without carrying legacy vendor columns.

This is a contract-freeze phase, not a documentation-portal or Config Studio phase.

## 2. Why this phase exists

Freezing configuration before external fixtures would fossilize design mistakes. Phases 046-048 have now exercised multiple topologies and performance. The core contract can be stabilized so future tools can safely consume PFETL's Pydantic models/schema.

## 3. Inherited repository state

Phase 048 guarantees:
- external household/investment configurations work;
- diagnostics are usable;
- performance is accepted;
- no known architecture migration remains.

Current SourceConfiguration has an explicit schema version but may still contain names/structures considered internal during refactor.

## 4. Current codebase anchors

Review all public models:
- SourceConfiguration;
- SourceConfig;
- SourceDatasetConfig;
- ProviderType;
- selectors;
- source schema declarations;
- mapping/normalization rules;
- change policies;
- identity strategies;
- CapabilityId/selection;
- DatasetId vocabulary;
- provider-generated dataset configuration where exposed.

Review CLI diagnostic output contracts only where they are intended for machine consumption.

## 5. Exact target state after this phase

Freeze `source_config` schema v1.

Required properties:
- stable serialized field names;
- documented required/default/optional semantics in model descriptions;
- discriminated unions have stable discriminator values;
- DatasetId/CapabilityId values stable;
- schema export is machine-readable (JSON Schema or Pydantic-native equivalent);
- unknown/removed fields follow explicit policy;
- future breaking changes require schema-version bump/migration;
- deprecation window/process defined for additive evolution.

Internal runtime classes such as ExecutionPlan internals need not become public merely because configuration references capabilities.

## 6. Detailed implementation sequence

### Step 1 - Public-surface inventory
Mark each model/field ENUM value PUBLIC or INTERNAL. Anything serialized in source config is public.

### Step 2 - Naming review from fixture experience
Fix awkward/ambiguous names now, before freeze. Update all fixtures/configs atomically.

### Step 3 - Validation/default review
Remove surprising implicit behavior. Defaults must be safe and semantically stable.

### Step 4 - Discriminator/version review
Ensure selector/normalization/identity unions serialize unambiguously.

### Step 5 - Export machine-readable schema
Generate deterministic schema artifact through supported project mechanism. Test it matches models and includes descriptions/constraints where available.

### Step 6 - Compatibility policy
Implement/test:
- current v1 loads;
- unsupported future/old breaking version fails with remediation;
- additive unknown-field behavior follows chosen policy;
- deprecated field handling explicit.

### Step 7 - Identifier freeze & Public Configuration Triumvirate Schema Freeze
DatasetId, ProviderType, CapabilityId and policy enum serialized values reviewed. Rename only now if essential.
Formally freeze the public schemas of the PFETL configuration triumvirate:
1. **`sources.toml` v1 Schema Freeze:** Freeze as a pure evidence catalog (sources, datasets, fields, normalizations). The transitional backwards-compatibility bridge for `capabilities` in `SourceConfiguration` is permanently eradicated.
2. **`settings.toml` v1 Schema Freeze:** Freeze as the authoritative runtime execution profile owning `[capabilities] enabled = [...]`, warehouse paths, and logging.
3. **`financial_rules.toml` v1 Schema Freeze:** Freeze capability-partitioned financial rules models (structured with canonical capability headings `[household]`, `[wealth]`, `[investments]`, `[benchmark]`, `[tax]`, `[fire]`) with machine-readable JSON Schema export. Migrate Shan's production `shan_personal_finance_rules.toml` to the finalized capability-headed structure.

### Step 7b - Demolition of Transitional column_master & DatasetId.COMMON_COLUMN_MASTER
Permanently eradicate all traces of transitional `column_master` from the public contract and codebase:
- Remove `column_master_csv` from default `SourceConfiguration` in `src/personal_finance_etl/config/sources/loader.py`.
- Demolish `DatasetId.COMMON_COLUMN_MASTER` from `src/personal_finance_etl/contracts/datasets.py` and eradicate `DatasetOrigin.TRANSITIONAL_CONFIGURATION_DATASET`.
- Demolish `COMMON_COLUMN_MASTER` from `BRONZE_CONTRACT_REGISTRY` in `src/personal_finance_etl/infrastructure/warehouse/contracts.py`, permanently reducing the Bronze contract count from 20 to the definitive 19 canonical financial contracts.
- Demolish canonical bronze schema `CANONICAL_BRONZE_COMMON_COLUMN_MASTER_SCHEMA` from `canonical_schemas.py`, canonical field sets from `canonical_fields.py`, hashing table entries from `hashing.py`, and capability bronze bindings from `capabilities.py`.
- Remove transitional runtime bypasses (`if ds_id == DatasetId.COMMON_COLUMN_MASTER: continue`) from `execution.py` and `bronze.py`.
- Demolish `tests/config/test_column_master_parity.py` and delete legacy `COLUMN_MASTER.csv` from `tests/fixtures/`.
- Update all test suites and topological guards (`test_topology.py`, `test_dataset_collection.py`, `test_admission_contracts.py`, `test_source_planner.py`, `test_admission_service.py`) to verify strictly 19 canonical Bronze contracts with zero transitional remnants.

### Step 7c - Shan Production Cutover to sources.toml & loader.py Hardcoding Demolition
Convert Shan's live production configuration in Google Drive to explicit TOML files and demolish all hardcoded Python configuration dictionaries:
1. **Author Production `shan_personal_finance_sources.toml` & `shan_personal_finance_sources_Test.toml`:**
   - In target directory `G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\`, generate:
     - `shan_personal_finance_sources.toml` (Production profile)
     - `shan_personal_finance_sources_Test.toml` (Test profile)
   - Declare all active Shan physical evidence sources:
     - SQLite source directory: `location = "G:\My Drive\MoneyManager"` (dynamic folder location using latest-modified file discovery to automatically bind the newest `.mmbak` or `.sqlite` backup file on every pipeline run, preserving `SOURCE_DB_FOLDER` semantics);
     - Typed table selectors for `zcategory`, `assetgroup`, `assets`, `currency`, and `inoutcome`;
     - Brokerage statements directory: `G:\My Drive\Docs\Financial Docs\Statements` with file pattern selectors for `Tradebook.xlsx`, `INDmoney_Holding.xlsx`, and `Mutual_Funds_Orders.xlsx`;
     - Static reference datasets directory: `G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\` declaring `OPENING_BALANCE.csv`, `BENCHMARK_MASTER.csv`, `BENCHMARK_MAPPING.csv`, `MF_ISIN_MAPPING.csv`, `MACRO_PARAMETERS.csv`, and `CURRENCY_MAPPING.csv`;
     - Pruned canonical column schemas established in Phases 046 & 047 (clean financial contracts without vendor baggage);
     - Zero references to retired `column_master`.
2. **Update `shan_personal_finance_ETL.toml` & `shan_personal_finance_ETL_Test.toml` (`Settings`):**
   - Cleanly prune all redundant source file paths (`COLUMN_MASTER_PATH`, `MF_ISIN_CSV_PATH`, `BENCHMARK_MAPPING_CSV_PATH`, `BENCHMARK_MASTER_CSV_PATH`, `MACRO_PARAMETERS_CSV_PATH`, `OPENING_BALANCE_CSV_PATH`, `CURRENCY_MAPPING_CSV_PATH`, `SOURCE_DB_FOLDER`, `STATEMENTS_FOLDER`) that are now owned by `sources.toml`.
   - Keep settings focused strictly on execution/storage environment (`TARGET_DB_BASE_PATH`, `TARGET_DB_NAME`, `RAW_DOCUMENT_STORE_NAME`, `LOGS_DIRECTORY`, `RETAIN_LAST_N_RUNS`, `FILE_HASH_POLICY`).
3. **Update `shan_personal_finance_rules.toml` (`FinancialRules`):**
   - Synchronize financial rules models with finalized capability IDs, tax schedules, inflation parameters, and withdrawal rates.
4. **Demolish Hardcoded Python Dictionaries from `loader.py`:**
   - Permanently delete all ~2,300 lines of hardcoded Python dictionaries from `src/personal_finance_etl/config/sources/loader.py`:
     - `get_shan_baseline_sources()`
     - `get_shan_baseline_dataset_bindings()`
     - `get_shan_baseline_source_configuration()`
     - all private field and mapping arrays (`_HOUSEHOLD_ASSETS_FIELDS`, etc.).
   - Reduce `loader.py` to a lean module containing strictly Pydantic schema models (`SourceConfiguration`, `SourceConfig`, `SourceDatasetConfig`) and parser/serializer methods (`from_toml`, `to_toml`).
   - Update `ServiceContainer.create_source_config()` to load exclusively from `sources.toml` (raising `FileNotFoundError` with clear remediation guidance if absent, rather than falling back to hardcoded code).
   - Add architecture guards in `tests/architecture/` verifying zero hardcoded `SourceConfig` instances exist in `src/`.

### Step 7d - Demolition of Transitional silver_column_dispositions.json & Historical Manifest Helpers
Permanently eradicate the transitional Silver column disposition JSON manifest and its associated code artifacts:
- Delete `src/personal_finance_etl/contracts/silver_column_dispositions.json`.
- Demolish `_load_silver_column_dispositions()`, `ALL_SILVER_COLUMN_DISPOSITIONS`, and `SILVER_COLUMN_DISPOSITIONS` from `src/personal_finance_etl/contracts/semantic_inventory.py` and `contracts/__init__.py`.
- Update all internal schema assertions to rely directly on the declarative DDL specifications (`SILVER_TABLE_SCHEMAS`, `GOLD_TABLE_SCHEMAS`) and Pandera canonical schemas established in Phases 043, 046, and 047.
- Add architecture AST guards in `tests/architecture/` asserting that `silver_column_dispositions.json` does not exist on disk and is never loaded.

### Step 8 - Golden configuration fixtures & User Starter Templates
Promote external household and investment configurations to schema-v1 golden examples and distribute frozen user starter templates under `examples/templates/`:
- `template_household_minimal.toml`: pure household budgeting and expense tracking (`[HOUSEHOLD_CORE]`).
- `template_household_wealth_fire.toml`: household balance sheet, net worth, savings rates, and FIRE milestones without stock portfolios (`[HOUSEHOLD_CORE, WEALTH, FIRE]`).
- `template_domestic_investor.toml`: domestic equity tradebooks, mutual fund folios, FIFO lots, and capital gains tax (`[HOUSEHOLD_CORE, INVESTMENT_ACCOUNTING, TAX]`).
- `template_global_investor.toml`: domestic + US equities, USD/INR foreign exchange, and index benchmarks (`[HOUSEHOLD_CORE, INVESTMENT_ACCOUNTING, BENCHMARK_ENRICHMENT, FOREIGN_ASSET_ENRICHMENT, TAX]`).
- `template_full_spectrum.toml`: comprehensive golden configuration exercising all 7 capabilities.

Automated tests must verify every template strictly conforms to the frozen JSON schema and passes dry-run admission without warning.

### Step 9 - Architecture guard
Future public model changes require schema/version/golden fixture updates.

### Step 10 - Final config migration test
If pre-freeze refactor configs differ, provide one-time migration guidance/tool only if users could plausibly have them; do not support every internal draft forever.

## 7. Files and symbols in scope

Modify:
- public Pydantic/source config models;
- schema export;
- version/compatibility validation;
- golden configs/tests;
- CLI schema/validation command if appropriate;
- purge all transitional column_master configuration, contracts, and tests.

Do not build docs portal or companion applications.

## 8. Cross-cutting impacts

**Persistence:** run snapshots continue storing exact config/fingerprint; schema version explicit.

**Identity:** serialized identity-strategy contract frozen, not financial ID algorithms.

**Observability:** enum values used in context remain stable where public/forensic.

**Performance:** none.

**Ecosystem:** future Config Studio may import/use this contract, but no Studio code is created.

## 9. Tests and verification

Required:
- complete public-surface inventory;
- deterministic machine-readable schema export;
- golden Excel/CSV/SQLite/domestic/foreign configs validate;
- production starter templates (`examples/templates/*.toml`) validate against schema v1 and pass dry run admission;
- version incompatibility failure;
- discriminator round trips;
- canonical serialization/fingerprint stability under v1;
- architecture guard for public changes;
- full Shan/external regression after any final renames.

## 10. Explicit non-goals

Do not:
- freeze internal implementation classes unnecessarily;
- build Config Studio;
- build docs portal;
- add analytics application;
- make a v11 release merely for contract freeze.

## 11. Completion checklist

- [ ] Public config surface identified.
- [ ] Final slimmed canonical column catalog frozen and published.
- [ ] Schema v1 field names finalized.
- [ ] Enum/discriminator values finalized.
- [ ] Machine-readable schema exported.
- [ ] Compatibility/deprecation policy implemented.
- [ ] Golden external configs pass.
- [ ] Starter templates distributed in `examples/templates/` and certified across capability archetypes.
- [ ] Fingerprinting remains deterministic.
- [ ] Future changes are guarded.
- [ ] Transitional column_master completely demolished and DatasetId.COMMON_COLUMN_MASTER purged (Bronze contracts permanently reduced to 19).
- [ ] Hardcoded configuration dictionaries demolished from loader.py; sources.toml is sole configuration authority.

## 12. Commit boundary

```text
feat(config): freeze source configuration v1
```

## 13. Handoff to Phase 050

Phase 050 may assume the public configuration contract is stable and all supported topology fixtures are golden. The final phase validates the complete experience from a clean installation using only public interfaces and frozen contracts.

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
