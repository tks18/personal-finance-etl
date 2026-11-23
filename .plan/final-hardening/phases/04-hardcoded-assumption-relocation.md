# Phase 04 — Hardcoded Assumption Relocation

**Sprint:** 2–3 hours  
**Goal:** implement the exact parameterization decisions already established by v11.3.1 archaeology. Do not perform a new open-ended literal hunt unless implementation exposes a directly adjacent duplicate.

Read the full matrix in the program README before coding.

## A. Settings model changes

### `config/settings.py`

Add:

```text
class PerformanceSettings(BaseModel):
    market_workers: int = 8
    isin_workers: int = 4
    duckdb_threads: int = 4

class MarketDataSettings(BaseModel):
    fetch_buffer_days: int = 15
    max_download_attempts: int = 3
    benchmark_anomalous_drop_threshold: float = -0.40
    fx_backward_fill_days: int = 30
    benchmark_max_staleness_days: int = 7
    us_price_max_staleness_days: int = 7
```

Extend `ObservabilitySettings`:

```text
max_age_days: int | None = 30
```

Add `performance` and `market_data` fields to root `Settings`.

Use Pydantic bounds where obvious:

- workers/threads >= 1;
- attempts >= 1;
- buffer/staleness days >= 0;
- anomalous drop threshold between -1.0 and 0.0;
- max age either null or >= 1.

Add `description=` to every new field for the later GUI editor.

### Wire consumers

- `application/pipeline/execution.py`: replace both `max_workers=8` constructions with `settings.performance.market_workers`.
- provider pipelines/extractors: pass `fetch_buffer_days` and `max_download_attempts` to `fetch_ticker_raw_history` instead of relying on defaults.
- `infrastructure/providers/market/benchmark.py::_check_anomalous_drops`: consume configured threshold.
- `domain/market/fx.py::FXRateProvider`: accept configured backward-fill days; replace range(1,31).
- `BenchmarkPriceProvider`: inject configured benchmark staleness.
- `_join_and_validate_prices`: inject configured US price staleness.
- `application/investments/isin_service/pipeline.py`: cap worker count with `settings.performance.isin_workers` rather than literal 4; preserve CPU-count safety.
- `DuckDBManager`: accept `duckdb_threads` through bootstrap construction; replace `PRAGMA threads=4`.
- `application/pipeline/lifecycle.py::teardown`: pass `observability.max_age_days` to `LogRetentionManager`.

Do not thread the entire Settings object into deep domain functions if a scalar parameter is sufficient. Resolve configuration at application/bootstrap boundaries and pass explicit values.

## B. FinancialRules model changes

### `config/financial_rules/household.py`

Add `ExpenseAnalyticsRules` under `ExpenseRules.analytics` with:

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

Add descriptions and sensible validation (>0 windows, positive multipliers/cap).

Add `IncomeGroupingRules` under `IncomeRules.grouping`:

```text
salary_category_name = "Salary"
allowance_name_pattern = "allowance"
allowance_group_name = "Allowances"
```

Extend `CashflowAssetRules`:

```text
investing_analysis_offset_months = -1
```

### `config/financial_rules/investments.py`

Extend `PortfolioManagementRules`:

```text
cost_basis_tolerance = 0.01
```

### `config/financial_rules/tax.py`

Extend `TaxAssumptions`:

```text
ltcg_maturity_ladder_days = [30, 90, 180, 365]
```

Validate exactly four strictly ascending positive values for this batch because the existing Gold output has four fixed bucket columns.

## C. Replace exact consumers

### Expense analytics

`domain/household/expense.py::_compute_spend_variances`

Replace literal 3/6/12 rolling windows, regex patterns, score cap and creep multipliers with `self.rules.expense.analytics`.

Keep YoY `.shift(12)` as algorithmic. Replace `30.4375` with a named code constant `AVERAGE_DAYS_PER_MONTH = 365.25 / 12.0`, not a config field.

### Income grouping

`domain/household/transforms/income_dimensions.py::transform_d_income_subcategory`

Replace `Salary`, `allowance`, `Allowances` literals with `rules.income.grouping` values.

### Investment transfer timing

`domain/household/transforms/transactions.py::transform_f_transfer_transactions`

Stop using `ASSET_GROUP == "Investments"` as the semantic test. Join/use the existing rule-derived investing classification (`cashflow_activity_type == "INVESTING"` or equivalent available field), then apply `rules.assets.cashflow.investing_analysis_offset_months`.

Do not add another configurable asset-group label.

### Reconciliation tolerance

Replace both `0.01` instances in:

- `domain/investments/reconciliation/engine.py`;
- `domain/investments/lots/reconciliation.py`.

Use `rules.portfolio_management.cost_basis_tolerance` through the existing reconciliation context. Remove exported `COST_BASIS_TOLERANCE` only if nothing public consumes it; otherwise deprecate internally without compatibility machinery.

### LTCG ladder

`application/investments/aggregation_service/service.py`

Read four values from `rules.assumptions.tax.ltcg_maturity_ladder_days` and use them in the existing fixed Gold columns. Keep column names unchanged.

## D. Eliminate duplicate financial fallbacks

Remove/replace literal policy fallbacks where authoritative FinancialRules already exists:

- 24-month generic LTCG fallback in `domain/market/macro.py`;
- `_DEFAULT_DEBT_MF_CUTOFF` policy fallback;
- 125000 / 0.05 / 0.05 / 0.30 macro fallbacks;
- `90` harvest wait fallback in `portfolio/analytics.py`;
- `"INR_INR"` `getattr` fallbacks in investment context/processor/snapshots.

Production financial paths should require FinancialRules rather than silently substituting stale policy.

## E. Update TOML fixtures/examples

Update the Phase-2 test `config.toml` and `financial_rules.toml` with every new field. Defaults may preserve current behavior, but explicit fixture values make the test oracle readable.

## Verification

1. Run the full numerical suite with default-equivalent values: every pre-existing golden number must remain identical.
2. Add at least one parameter sensitivity test for each new rule/settings group proving a changed value changes only the expected behavior.
3. Confirm Settings and FinancialRules fingerprints include all new fields automatically via existing `model_dump`/export paths.
4. Confirm Meta/config auditing records the new values.

## Exit criteria

- no listed hardcoded user assumption remains at its old consumer;
- changing a supported assumption requires TOML/UI, not source edits;
- algorithmic constants listed in README remain code-owned;
- default-equivalent configuration preserves financial outputs.
