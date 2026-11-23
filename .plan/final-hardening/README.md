# PFETL Core Maintenance & Usability Program

**Implementation authority:** `personal_finance_etl_11.3.1.zip` supplied by Shan on 23 Nov 2026.

**How to implement:** read this README first, then read **only the active phase file** under `phases/`. Those two files are the authority for the active sprint. Do not revive the abandoned Grand Refactor, the earlier v11 PySide6 plan, or old planning documents.

## 1. Program objective

Keep PFETL's financial and operational sophistication, while removing maintenance work that does not help Shan run and understand his monthly finances.

The target is deliberately simple:

```text
financial correctness and evidence        KEEP / PROTECT
observability + Control Plane + recovery  KEEP / PROTECT
CustomTkinter desktop                     KEEP / IMPROVE
operator CLI                              KEEP / CLEAN
historic phase tests                      REPLACE
large docs + Wiki maintenance             REMOVE
low-value CI/config clutter               REMOVE
hardcoded user assumptions                CONFIGURE
Analytics Studio                          SEPARATE FUTURE REPO
```

The program has **8 small implementation phases**, each intended to fit a focused 2–3 hour sprint. A phase can stop early if its exit criteria are green. Do not expand a phase simply because adjacent cleanup is visible.

## 2. v11.3.1 archaeology snapshot

The supplied repository currently contains:

- 35 `tests/test_*.py` modules, mostly historical phase/certification tests;
- 57 files under `docs/`, of which 55 are Markdown;
- a 737-line root README;
- `application/operator.py` at 589 lines;
- CustomTkinter UI in `presentation/desktop/app.py` (521 lines) and `base_tab.py` (295 lines);
- 20 Bronze, 24 Silver and 22 Gold contracts;
- one `pfetl` CLI entrypoint;
- mature JSONL forensic observability;
- the six v11 analytical additions already present in production code.

This program **does not change Bronze/Silver/Gold topology, FIFO methodology, Tax methodology, FIRE methodology, deterministic IDs, Control Plane schema, Raw Store semantics, or observability event architecture** unless a phase explicitly says otherwise.

## 3. Current architectural issue: OperatorService

`src/personal_finance_etl/application/operator.py` currently imports and directly uses:

- `sqlite3`;
- `duckdb`;
- `urllib.request`;
- `FileLock`;
- `PreferencesManager`;
- raw Control Plane SQL against `cp_runs` and `cp_sync_summaries`;
- filesystem size/path inspection.

`OperatorService` should remain the application use case, but concrete inspection belongs in infrastructure. Phase 1 moves the mechanics while preserving the public `SystemStatus`, `SystemInfo`, `DoctorCheckResult`, and `DoctorReport` behavior.

## 4. Replacement test philosophy

The current suite is heavy on migration history. Examples include `test_phase3_*`, `test_phase4_*`, `test_phase5_*`, through `test_phase13_*`, plus constitutional certification tests.

The replacement suite must answer a different question:

> Does PFETL still produce the correct financial and operational outputs end to end?

The target suite is intentionally small:

```text
tests/
├── fixtures/
│   ├── config.toml
│   ├── financial_rules.toml
│   └── deterministic source fixtures
├── test_pipeline_e2e.py
├── test_household_golden.py
├── test_investment_fifo_golden.py
├── test_tax_fx_benchmark_golden.py
├── test_wealth_fire_golden.py
└── test_operational_integrity.py
```

### Required numerical assertions

The tests must assert actual values, not merely schemas:

- household income, expenses, core expenses, transfers, cashflow and net worth;
- purchase/sale/lot IDs, quantities, FIFO cost basis and realized gain/loss;
- FX conversion, asset PnL, FX PnL, benchmark performance and active return;
- Tax holding type, applied rate, estimated tax, exemption treatment;
- wealth/FIRE values and deterministic simulation invariants;
- Control Plane success state, Gold publication, JSONL creation and protected-ID determinism.

The fixture must be small enough that expected numbers can be calculated and reviewed by hand.

## 5. Documentation and tooling cleanup already proven by archaeology

Before deleting `docs/`, move application assets because runtime code still uses:

```text
presentation/desktop/app.py
  resource_path("docs/assets/images/logo.png")
  resource_path("docs/assets/images/logo.ico")

main.spec
  ('docs/assets/images', 'docs/assets/images')
  icon='docs/assets/images/logo.ico'
```

Move the two app assets to:

```text
src/personal_finance_etl/presentation/assets/logo.png
src/personal_finance_etl/presentation/assets/logo.ico
```

Then update packaging/runtime references and delete `docs/`.

Delete these requested root files:

```text
.bandit
.codacy.yml
.coderabbit.yaml
.flake8
.prospector.yml
```

Also clean their surviving references:

- remove `[tool.bandit]` from `pyproject.toml`;
- remove `Documentation = .../docs/README.md` from `[project.urls]` or point it to the root README;
- remove stale `flake8` hidden imports from `main.spec` if they serve no packaging purpose;
- remove `# flake8: noqa` from `scripts/*.py` and `tests/run_headless.py` if those files survive Phase 2;
- remove deleted filenames from `scripts/auto_commit.py`;
- replace all root README links/badges pointing to docs, Codacy, CodeRabbit or Wiki/DeepWiki during Phase 8.

`MANIFEST.in` currently contains `include docs/manifest.json`; remove it.

## 6. Full Settings / FinancialRules archaeology

The objective is **not** to parameterize every literal. Parameterize values Shan may reasonably want to change without changing the algorithm. Keep mathematical/calendar identities in code.

### 6.1 Existing Settings that are already correctly configurable

`config/settings.py` already owns:

- database base path, DuckDB filename, Raw Store filename;
- `disable_file_discoverer`;
- nine source paths;
- five statement discovery patterns;
- three evidence hash policies;
- logs directory;
- retained run count.

Do not duplicate these elsewhere.

### 6.2 New Settings parameters to add

#### `ObservabilitySettings`

| New field | Current hardcode | Source | Reason |
|---|---:|---|---|
| `max_age_days` | `30` | `infrastructure/observability/retention.py::LogRetentionManager` | user-facing retention policy already supported by implementation but not exposed by Settings |

Update `application/pipeline/lifecycle.py::teardown()` to pass both `retain_last_n_runs` and `max_age_days`.

#### `PerformanceSettings` (new `Settings.performance`)

| New field | Current hardcode | Current consumer |
|---|---:|---|
| `market_workers` | `8` | `application/pipeline/execution.py::process_currency`, `process_us_market_data`; provider extractors default to 8 |
| `isin_workers` | `4` cap | `application/investments/isin_service/pipeline.py` uses `min(4, os.cpu_count() or 1)` |
| `duckdb_threads` | `4` | `infrastructure/warehouse/connection.py::DuckDBManager.open` |

Keep DuckDB memory calculation automatic (`75%`, minimum 4 GB) unless real usage proves a need to expose it. It adapts to the machine and is not a recurring personal assumption.

#### `MarketDataSettings` (new `Settings.market_data`)

| New field | Current hardcode | Current consumer |
|---|---:|---|
| `fetch_buffer_days` | `15` | `infrastructure/providers/market/common.py::fetch_ticker_raw_history` |
| `max_download_attempts` | `3` | same function / `download_yfinance_history` |
| `benchmark_anomalous_drop_threshold` | `-0.40` | `infrastructure/providers/market/benchmark.py::_check_anomalous_drops` |
| `fx_backward_fill_days` | `30` | `domain/market/fx.py::FXRateProvider.get_rate` |
| `benchmark_max_staleness_days` | `7` | `domain/investments/valuation/benchmark.py::BenchmarkPriceProvider` |
| `us_price_max_staleness_days` | `7` | `domain/investments/valuation/market_state.py::_join_and_validate_prices` |

These are evidence acceptance / provider policies, not Tax or portfolio methodology, so they belong in Settings rather than FinancialRules.

### 6.3 Existing FinancialRules that already cover real assumptions

The current models already correctly own:

- income classification IDs;
- core expense IDs;
- asset liquidity/cashflow roles;
- investment category/subcategory mappings;
- budget allocations, overspend threshold, emergency-fund months and income smoothing;
- rebalance tolerance;
- macro fallbacks;
- FIRE assumptions;
- Monte Carlo and stochastic parameters;
- Tax cutoff/rates/holding periods/head mappings/exclusions;
- CMA assumptions and target allocations;
- default currency and mutual-fund scheme mappings.

Do not create parallel settings for them.

### 6.4 New FinancialRules parameters to add

#### Expense analytical policy

Current hardcodes in `domain/household/expense.py::_compute_spend_variances`:

- rolling windows `3`, `6`, `12`;
- investment category regex `invest|saving`;
- fixed-expense regex `fixed|utilities|rent|insurance|tax|emi|loan`;
- consistency score cap `10.0`;
- creep spend multiplier `1.15`;
- creep frequency multiplier `1.10`;
- large-spike multiplier `1.50`.

Add under `expense.analytics`:

```text
short_window_months = 3
medium_window_months = 6
long_window_months = 12
investment_group_patterns = ["invest", "saving"]
fixed_group_patterns = ["fixed", "utilities", "rent", "insurance", "tax", "emi", "loan"]
consistency_score_cap = 10.0
creep_spend_multiplier = 1.15
creep_frequency_multiplier = 1.10
creep_spike_multiplier = 1.50
```

Do **not** parameterize `30.4375` as a user setting. Replace it with a named domain constant such as `AVERAGE_DAYS_PER_MONTH = 365.25 / 12.0` to explain the algorithm.

#### Income grouping policy

Current hardcode in `domain/household/transforms/income_dimensions.py::transform_d_income_subcategory`:

```text
CATEGORY_NAME_SHORT == "Salary"
CATEGORY_NAME contains "allowance"
→ CATEGORY_GROUPS = "Allowances"
```

Add under `income.grouping`:

```text
salary_category_name = "Salary"
allowance_name_pattern = "allowance"
allowance_group_name = "Allowances"
```

This is a personal category-label convention and should not require source code edits.

#### Transfer analysis timing

Current hardcode in `domain/household/transforms/transactions.py::transform_f_transfer_transactions`:

```text
ASSET_GROUP == "Investments" → ADJUSTED_DATE_FOR_ANALYSIS = DATE - 1 month
```

Do not add another hardcoded name to rules. Reuse the existing rule-derived `cashflow_activity_type == "INVESTING"` / `ledger_role == "INVESTING_ASSET"` from the asset dimensions, and add one policy field:

```text
assets.cashflow.investing_analysis_offset_months = -1
```

The category identity stays in the existing `assets.cashflow.investing_activities` mapping.

#### Reconciliation tolerance

Current duplicate hardcodes:

- `domain/investments/reconciliation/engine.py::COST_BASIS_TOLERANCE = 0.01`;
- `domain/investments/lots/reconciliation.py` compares `abs(our_avg-target_avg) <= 0.01`.

Add:

```text
portfolio_management.cost_basis_tolerance = 0.01
```

Both consumers must use the same rule value.

#### LTCG maturity ladder

Current hardcodes in `application/investments/aggregation_service/service.py` are `30`, `90`, `180`, `365` days.

Add under Tax assumptions:

```text
ltcg_maturity_ladder_days = [30, 90, 180, 365]
```

The Gold column names currently encode these buckets (`LTCG_Maturing_30D`, etc.). For this batch, keep the existing four output columns and validate that the configured list contains exactly four ascending positive values. Do not redesign Gold dynamically.

### 6.5 Hardcoded fallbacks to eliminate, not parameterize again

Several domain paths already have an authoritative FinancialRules field but still contain fallback literals. Remove the duplicate literal and require/use the configured value:

| Current fallback | File | Correct authority |
|---|---|---|
| `24` months | `domain/market/macro.py::get_ltcg_threshold_months` | `assumptions.tax.ltcg_threshold_months`; missing mapping should use an explicit configured default or fail clearly |
| `2023-04-01` | `domain/market/macro.py::_DEFAULT_DEBT_MF_CUTOFF` | `assumptions.tax.debt_mf_cutoff_date` |
| `125000.0` | `domain/market/macro.py` | `fallback_equity_ltcg_exemption` |
| `0.05` risk-free | `domain/market/macro.py` | `assumptions.macro.fallback_risk_free_rate` |
| `0.05` inflation | `domain/market/macro.py` | `assumptions.macro.fallback_inflation_rate` |
| `0.30` ordinary rate | `domain/market/macro.py` | `assumptions.macro.fallback_ordinary_income_rate` |
| `90` harvest wait | `domain/investments/portfolio/analytics.py` | `assumptions.tax.harvest_wait_days_threshold` |
| `"INR_INR"` fallback via `getattr` | investment context/processor/snapshots | `FinancialRules.DEFAULT_CURRENCY_ID` |

The root `FinancialRules` object is required for production financial execution. Prefer explicit failure to silent policy substitution.

### 6.6 Hardcodes that should stay in code

Do not turn these into TOML knobs:

- 12 months for YoY comparisons;
- 365/365.25 day annualization identities;
- month arithmetic and Indian financial-year calendar mechanics;
- FIFO chronological ordering;
- transaction type codes needed to interpret the known household source contract;
- event/progress percentages used only for UI progress;
- queue polling intervals;
- SQLite lock/busy timeouts unless operational evidence proves they need tuning;
- JSONL buffer size/compression constants unless there is an observed problem;
- `pipeline.lock` filename;
- diagnostic sample limits (e.g. `.limit(10)`).

### 6.7 Additional source-taxonomy hardcodes: improve only where low-risk

The code still contains `__file_category__ == "US Stocks"` in market paths and regex-based investment-class buckets in `domain/household/cashflow/summary.py`. These are maintenance smells, but they are not required to complete the user's requested configurability work safely.

For this batch:

- do not redesign Silver/Gold or source taxonomy;
- centralize `US Stocks` as one internal constant or replace with an existing canonical classification only if equivalence is obvious and covered by the new golden suite;
- parameterize the user-facing household expense/category heuristics listed above;
- defer broader source taxonomy cleanup unless it blocks the UI/configuration goals.

## 7. CustomTkinter target grounded in current code

Current UI has one `UnifiedETLTab` that builds the header, two TOML path combo boxes, Run/Snapshot/Restore buttons, a progress bar and a narrative log. Keep CustomTkinter and reuse `PersonalFinanceEngine`.

Target top-level structure:

```text
presentation/desktop/
├── app.py                 # window + top-level tab navigation only
├── base_tab.py            # shared event/log helpers
├── run_tab.py             # current Run/Snapshot/Restore experience
├── settings_tab.py        # Settings TOML editor
├── financial_rules_tab.py # FinancialRules TOML editor
├── logs_tab.py            # narrative + forensic JSONL viewer
├── system_tab.py          # status/info/doctor
├── config_editor.py       # reusable Pydantic field renderer (small, not a framework)
├── theme.py
└── assets/
    ├── logo.png
    └── logo.ico
```

Use a `CTkTabview` with four user-facing tabs:

```text
Run | Configuration | Logs | System
```

Configuration can contain Settings / Financial Rules sub-tabs.

### TOML write path

Python's `tomllib` is read-only. Add **one** small dependency: `tomlkit`. Use it to update the selected TOML while preserving comments/order where possible. Validation sequence is always:

```text
UI values
→ build Python dict
→ Settings.model_validate / FinancialRules.model_validate
→ update TOML document
→ write temp file
→ reload from temp file
→ atomic replace original
→ add to recents
```

Never write an invalid model over the user's existing file.

### UI metadata

Use Pydantic `Field(description=...)` as the source of guidance text. Add missing descriptions to Settings and classification-rule fields during Phases 4–6. UI-specific metadata may use a tiny `json_schema_extra` convention only where widget type cannot be inferred:

```text
ui_widget: path | directory | enum | percentage | integer | text | list | matrix
unit: days | months | years | percent | INR | count
```

Do not build an external form schema.

## 8. Forensic JSONL viewer grounded in current event schema

`JsonlForensicSink` writes `ObservabilityEvent.to_dict()` one event per line. The viewer should display existing fields, not invent another log model.

Filterable columns:

- timestamp;
- severity;
- event_code;
- outcome;
- presentation_kind;
- message;
- `context.run_id`;
- `context.stage`;
- component;
- operation;
- entity type/id;
- provider;
- worker/batch;
- duration;
- rows;
- cache hit.

Detail pane:

- complete context;
- parent/operation IDs for lineage;
- settings/rules fingerprints;
- error failure domain;
- exception type/message;
- traceback summary;
- remediation hint;
- retryability;
- context variables.

Read files from `Settings.resolve_logs_dir()`. Sort by modification time. Do not persist a second log database.

## 9. System view grounded in existing operator API

After Phase 1, the GUI should call the existing façade methods:

```text
PersonalFinanceEngine.get_system_status(config_path)
PersonalFinanceEngine.get_system_info(config_path)
PersonalFinanceEngine.run_doctor(config_path, rules_path)
```

Do not query SQLite/DuckDB from presentation.

Display:

- lock state;
- DuckDB/Raw Store presence and sizes;
- latest run ID/status/timestamps;
- latest sync summary;
- stale/recovery-required counts;
- source paths/runtime metadata;
- Bronze/Silver/Gold contract counts;
- Doctor PASS/WARN/FAIL cards with remediation text.

## 10. Phase map

| Phase | Sprint | Outcome |
|---|---|---|
| 01 | 2–3h | decouple OperatorService concrete inspection from application |
| 02 | 2–3h | replace historical phase tests with a small numerical golden/E2E suite |
| 03 | 2–3h | remove docs/Wiki/tooling maintenance baggage safely |
| 04 | 2–3h | implement the exact Settings/FinancialRules parameterization matrix above |
| 05 | 2–3h | Settings TOML editor in CustomTkinter |
| 06 | 2–3h | FinancialRules TOML editor in CustomTkinter |
| 07 | 2–3h | forensic JSONL viewer + System operator UI |
| 08 | 2–3h | full production acceptance, dead-code cleanup and compact README |

## 11. Cross-program stop rules

Stop and reassess rather than inventing architecture if any phase starts requiring:

- new warehouse layers or table restructuring;
- a generic plugin/config framework;
- another UI toolkit;
- a local REST API;
- a second observability store;
- a test framework that recreates the deleted historical certification suite;
- a documentation hierarchy beyond the final concise README;
- changes to FIFO/Tax/FIRE methodology not required by the explicit parameter relocation matrix.

## 12. Program acceptance

The batch is complete only when:

1. the small numerical test suite is green;
2. Shan's real monthly dataset completes end to end;
3. core totals and protected financial IDs match the pre-batch oracle except where a deliberately changed configurable assumption is exercised;
4. the GUI can select, validate, edit, save and switch Settings and FinancialRules files;
5. recent config/rules behavior still works;
6. JSONL traces are readable/filterable in the GUI;
7. status/info/doctor are visible in the GUI without direct persistence access from presentation;
8. `docs/` and requested root maintenance files are gone;
9. the root README is concise and describes the application as it exists after this batch.
