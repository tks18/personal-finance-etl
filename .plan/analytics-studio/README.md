# PFETL Analytics Studio — Authoritative Implementation Program
**Upstream archaeology authority:** PFETL `v11.3.1` source snapshot supplied by Shan, plus the already-approved PFETL Core 8-phase maintenance/usability target. Analytics Studio starts only after that Core batch is complete and is implemented against the completed Core profile surface described below.
**Implementation authority:** read this README first, then read only the active file under `phases/`. The pair **`README.md + active phase file`** is the complete implementation authority. Earlier chats, discarded plans, or implementation ideas do not override that pair. Do not create extra planning/governance documents unless Shan explicitly asks.
## 1. Product mission
PFETL Analytics Studio is a **local-first, Shan-first, read-only analytical consumer** of PFETL. PFETL Core calculates financial truth; Studio turns that truth into exploration, visualizations, drill-downs, operational intelligence, and downloadable reports.
```text
PFETL Core                                 PFETL Analytics Studio
──────────                                 ──────────────────────
source evidence                            same Settings TOML + FinancialRules TOML
      ↓                                    resolve profile paths
Control Plane + Raw Store                  ↓
      ↓                            DuckDB + Control Plane + archived run JSONL
Bronze → Silver → Gold                     ↓ read-only
      ↓                            dashboards / explorers / reports
financial truth                            ↓
                                     PDF / XLSX / CSV / PNG/SVG
```
### Hard boundary
- Studio **never** writes PFETL DuckDB, Control Plane, Raw Store, Settings TOML, or FinancialRules TOML.
- Studio never reimplements FIFO, tax classification, reconciliation, XIRR, FX attribution, FIRE methodology, Monte Carlo methodology, deterministic IDs, or Gold methodology.
- Studio may safely aggregate already-canonical facts, slice existing metrics, compare periods, render charts, and generate presentation-only scenarios clearly labelled as non-canonical.
- Studio writes only its own state database containing recent profiles, saved views, saved report definitions and report-generation history.
## 2. Personalized input model — no second configuration universe
The Studio has exactly two user-selected profile inputs:

1. the same PFETL **Settings TOML** used by Core;
2. the same PFETL **FinancialRules TOML** used by Core.

There is no Analytics Studio config TOML. From Settings, Studio resolves:

- `database.target_db_base_path`;
- `database.target_db_name` → PFETL DuckDB warehouse;
- `database.raw_document_store_name` → SQLite Control Plane / Raw Store;
- `observability.logs_directory` → optional filesystem trace fallback;
- source paths and operating settings for profile/context display.
For historical truth, the selected TOML files are **not** assumed to be what produced the warehouse. Each PFETL run links to immutable `cp_settings_snapshots` and `cp_rules_snapshots`. Studio uses those snapshots as the authoritative assumptions for run-specific analysis and report provenance.
### Profile drift check
On profile open, Studio parses the selected TOMLs and compares their explicitly supplied leaves with the latest successful run snapshots. Show one of:

- **MATCH** — explicit selected-file values match latest run snapshot;
- **DRIFTED** — one or more selected values differ from the latest successful run;
- **UNVERIFIED DEFAULTS** — the run snapshot contains effective defaults absent from the raw TOML; explicit values still match.

This avoids pretending a changed rules file has already been applied to the warehouse.
### 2.1 Expected PFETL profile surface after the Core 8-phase batch

The current v11.3.1 model was archaeologized and the already-approved Core batch extends it. Studio should be implemented against the **completed Core model**, with a startup compatibility check rather than copying these fields into a second schema.

Expected Settings shape:

```text
Settings
├── database
│   ├── target_db_base_path
│   ├── target_db_name
│   ├── raw_document_store_name
│   └── disable_file_discoverer
├── sources
│   ├── household_database
│   ├── statements_root
│   ├── column_master
│   ├── mutual_fund_instrument_mapping
│   ├── instrument_master
│   ├── benchmark_master
│   ├── currency_reference
│   ├── financial_year_parameters
│   └── opening_balances
├── statement_patterns
│   ├── stock_pl
│   ├── mf_holdings
│   ├── stock_orders
│   ├── mf_orders
│   └── us_stock_transactions
├── hash_policy
│   ├── household_database
│   ├── statements
│   └── reference_data
├── observability
│   ├── logs_directory
│   ├── retain_last_n_runs
│   └── max_age_days                  # added by Core batch
├── performance                       # added by Core batch
│   ├── market_workers
│   ├── isin_workers
│   └── duckdb_threads
└── market_data                       # added by Core batch
    ├── fetch_buffer_days
    ├── max_download_attempts
    ├── benchmark_anomalous_drop_threshold
    ├── fx_backward_fill_days
    ├── benchmark_max_staleness_days
    └── us_price_max_staleness_days
```

Expected FinancialRules domains:

```text
FinancialRules
├── income
│   ├── active.category_ids / sub_category_ids
│   ├── dividends.category_ids / sub_category_ids
│   ├── interest.category_ids / sub_category_ids
│   ├── non_cash.category_ids / sub_category_ids
│   └── grouping                       # added by Core batch
│       ├── salary_category_name
│       ├── allowance_name_pattern
│       └── allowance_group_name
├── expense
│   ├── core.category_ids / sub_category_ids
│   └── analytics                      # added by Core batch
│       ├── short_window_months
│       ├── medium_window_months
│       ├── long_window_months
│       ├── investment_group_patterns
│       ├── fixed_group_patterns
│       ├── consistency_score_cap
│       ├── creep_spend_multiplier
│       ├── creep_frequency_multiplier
│       └── creep_spike_multiplier
├── assets
│   ├── illiquid
│   ├── cashflow
│   │   ├── cash_pools
│   │   ├── non_cash_pnl_sources
│   │   ├── working_capital_conduits
│   │   ├── investing_activities
│   │   ├── financing_liabilities
│   │   └── investing_analysis_offset_months  # Core batch
│   └── digital
├── investments[<instrument-family>]
│   └── category_ids / sub_category_ids
├── budget
│   ├── income_allocation: core/non-core/investment percentages
│   ├── alerts: overspend threshold, emergency-fund months
│   └── smoothing: income smoothing months
├── portfolio_management
│   ├── rebalance_tolerance_pct_points
│   └── cost_basis_tolerance           # Core batch
├── assumptions
│   ├── macro: trading days + inflation/risk-free/ordinary-income fallbacks
│   ├── fire: SWR, Coast/Lean FI, CAPE bounds, human-capital inputs
│   ├── monte_carlo
│   │   ├── iterations / max_months / volatility / real-return floor / target age / DOB
│   │   ├── markov_regime
│   │   ├── human_capital
│   │   ├── glide_path
│   │   ├── jump_diffusion
│   │   ├── guyton_klinger
│   │   └── inflation_model
│   ├── tax
│   │   ├── debt_mf_cutoff_date
│   │   ├── harvest_wait_days_threshold
│   │   ├── ltcg_threshold_months
│   │   ├── fallback_equity_ltcg_exemption
│   │   ├── rates
│   │   ├── heads_of_income / residual_income / exempt_income
│   │   ├── investment_exclusions
│   │   └── ltcg_maturity_ladder_days  # Core batch
│   ├── cma: expected_real_return / fat_tail_multiplier
│   └── target_allocations
├── DEFAULT_CURRENCY_ID
└── MF_SCHEME_MAPPINGS
```

Studio uses these values in three ways only: **profile context**, **target/reference overlays** (for example budget allocations or target portfolio allocations), and **report provenance**. It does not execute their financial methodology. Historical pages/report blocks always prefer the FinancialRules snapshot linked to the selected PFETL run over the currently selected TOML.

## 3. Concurrency and read-only safety
DuckDB is opened with `read_only=True`. SQLite uses URI read-only mode (`mode=ro`). Before any DuckDB connection, Studio checks the PFETL `pipeline.lock` in `target_db_base_path`. If Core is actively writing, Studio does **not** open DuckDB; it may still show profile context and Control Plane/log history where safe.

This is intentional because PFETL and Studio are separate processes. Do not invent a remote database, Quack server, copy-on-read warehouse, or synchronization service for one local user.
## 4. Chosen stack and dependency policy
Analytics Studio is deliberately a **Python-only local application**. It must feel polished and enterprise-grade without creating a second frontend ecosystem.

| Concern | Choice | Implementation rule |
|---|---|---|
| Python | **Python >=3.13** | Align with PFETL Core's runtime generation; lock exact environment with `uv.lock` |
| UI | **NiceGUI >=4,<5**, browser-local mode | Python-first UI; bind only to localhost; no native wrapper in v1 |
| Charts | **Plotly >=7.1,<8** | Interactive finance charts, hover/drill context, static-export support |
| Warehouse access | **DuckDB Python >=1.5.5,<2** | Read-only connections only; do not mutate PFETL |
| Operational store | built-in **sqlite3** | SQLite URI `mode=ro` for Control Plane/Raw Store |
| Dataframes | **Polars >=2.1,<3** | Final shaping/export; push large grouping/filtering into DuckDB SQL |
| Models | **Pydantic >=2.14,<3** | Profile, filter, semantic, saved-view and report models |
| Studio state | built-in **SQLite** + `platformdirs` | Only Studio-owned persistence |
| PDF | **ReportLab >=5.1,<6** | Deterministic local PDF composition, no browser screenshots |
| Static charts | **Kaleido >=1.5,<2** | Plotly → PNG/SVG; Chrome/Chromium prerequisite checked at runtime |
| Excel | **XlsxWriter >=3.3,<4** | Polished XLSX with provenance sheets and chart images |
| TOML input | built-in **tomllib** | Read PFETL Settings/FinancialRules; never edit them |
| Quality | **pytest + Ruff + mypy** | One focused quality gate, no tooling zoo |
| Packaging | `pfetl-studio` console script | Starts localhost UI and opens browser; no Docker/Node/PyInstaller requirement |

### Dependency rules
- Use `uv` and commit `uv.lock`.
- Pin compatible major ranges in `pyproject.toml`; the lockfile freezes actual builds.
- Do not depend on the `personal_finance_etl` Python package. Repositories remain independently deployable.
- DuckDB compatibility is checked against the actual PFETL file/schema at startup, not by importing Core code.
- Do not add pandas unless a concrete library requires it and Polars/DuckDB cannot serve the need.
- Do not add FastAPI routes, React, Node, a REST API, Redis, Celery, Docker, or a native wrapper in v1.

Current planning verification (23 Nov 2026) found NiceGUI 4.0.0, Plotly 7.1.0, Polars 2.1.0, Pydantic 2.14.4, Kaleido 1.5.2, XlsxWriter 3.3.4 and ReportLab 5.1.0 available. The project uses compatible ranges rather than hardcoding those patch releases.

## 5. Target repository and ownership
The finished repository remains intentionally compact. There is **one root README and no `docs/` tree or Wiki**.

```text
pfetl-analytics-studio/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .python-version
├── .gitignore
├── ruff.toml
├── mypy.ini
├── .github/
│   └── workflows/
│       └── quality.yml
├── src/
│   └── pfetl_analytics_studio/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── app.py
│       ├── profile.py
│       ├── state.py
│       ├── data/
│       │   ├── __init__.py
│       │   ├── duckdb_reader.py
│       │   ├── control_plane_reader.py
│       │   ├── log_reader.py
│       │   ├── catalog.py
│       │   └── cache.py
│       ├── semantic/
│       │   ├── __init__.py
│       │   ├── periods.py
│       │   ├── filters.py
│       │   ├── metrics.py
│       │   └── datasets.py
│       ├── analytics/
│       │   ├── __init__.py
│       │   ├── overview.py
│       │   ├── household.py
│       │   ├── wealth.py
│       │   ├── investments.py
│       │   ├── tax.py
│       │   ├── fire.py
│       │   ├── operations.py
│       │   └── explorer.py
│       ├── pages/
│       │   ├── __init__.py
│       │   ├── overview.py
│       │   ├── household.py
│       │   ├── wealth.py
│       │   ├── investments.py
│       │   ├── tax.py
│       │   ├── fire.py
│       │   ├── operations.py
│       │   ├── explorer.py
│       │   └── reports.py
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── registry.py
│       │   ├── service.py
│       │   ├── pdf.py
│       │   ├── excel.py
│       │   ├── builtins_household.py
│       │   ├── builtins_investments.py
│       │   └── builtins_operations.py
│       └── ui/
│           ├── __init__.py
│           ├── theme.py
│           ├── layout.py
│           ├── cards.py
│           ├── charts.py
│           ├── tables.py
│           ├── selectors.py
│           └── formatting.py
└── tests/
    ├── fixtures/
    │   ├── build_fixture_profile.py
    │   └── expected/
    ├── test_profile_connections.py
    ├── test_catalog_compatibility.py
    ├── test_semantic_queries.py
    ├── test_investment_queries.py
    ├── test_operations_forensics.py
    ├── test_explorer.py
    ├── test_reports.py
    └── test_smoke.py
```

### Package ownership
- `profile.py`: PFETL Settings/Rules selection, path resolution, current-vs-run snapshot drift and profile metadata.
- `state.py`: Studio SQLite schema and only Studio-owned persistence.
- `data/`: all external I/O. **Only this package opens DuckDB, Control Plane SQLite or archived/filesystem logs.**
- `semantic/`: period/filter/metric/dataset metadata. It describes safe presentation semantics, never PFETL methodology.
- `analytics/`: typed analytical read services and SQL/query definitions. No NiceGUI widgets here.
- `pages/`: thin NiceGUI composition only. No raw SQL, no DB connections, no financial calculations.
- `reports/`: report definitions, rendering and exporters. Report templates consume registered analytics/saved views; they do not bypass the analytics layer.
- `ui/`: reusable purely presentational components and formatting.

Do not reproduce PFETL's `application/domain/infrastructure/presentation` layering. Studio is a consumer app; this ownership model is enough.

## 6. Engineering constitution
### 8.1 Dependency direction
```text
pages ───────► analytics ───────► data
  │                │               │
  ├────────► semantic              └──► PFETL read-only stores
  ├────────► ui
  └────────► reports ─────► analytics / semantic / ui-formatting

profile ─────► data path resolution + state
state ───────► Studio SQLite only
```

Forbidden:
- `pages` importing `duckdb`, `sqlite3` or opening files;
- `ui` importing analytics/data packages;
- `data` importing NiceGUI;
- `reports` recomputing PFETL finance formulas;
- `analytics` writing PFETL or Studio state;
- any package importing PFETL Core Python internals.

### 8.2 Financial truth rule
A Studio calculation is allowed only when it is one of:
1. filtering existing canonical rows;
2. grouping/summing an **additive** registered measure at a compatible grain;
3. presentation comparison such as period delta/percentage change over already-canonical values;
4. display-only scenario sensitivity explicitly labelled non-canonical.

Never recompute FIFO, realized basis, tax classification, XIRR, benchmark methodology, FX attribution, reconciliation, FIRE or Monte Carlo results.

### 8.3 SQL rules
- Parameterize values; never string-concatenate user values into SQL.
- Dynamic identifiers must come from the runtime catalog/semantic registry whitelist.
- Prefer one named query function per analytical question over giant generic query builders.
- Pages and report definitions never contain SQL.
- Advanced SQL accepts a **single** `SELECT`/`WITH` statement on a read-only connection and rejects write/DDL/attach/install/load/export/copy statements.

### 8.4 Typing and code quality
- Type all public functions/methods and Pydantic models.
- Avoid `Any`; permit it only at library/raw-JSON boundaries and narrow immediately.
- Prefer immutable/frozen Pydantic models for filter/report definitions where practical.
- Use domain-specific names rather than `data`, `result`, `thing`, `handler` when a clearer name exists.
- Target modules under ~500 lines. Split only when ownership becomes mixed; do not create tiny files solely to satisfy a line count.
- Target functions under ~60 lines unless a cohesive report/layout composition is clearer intact.
- Raise typed Studio exceptions with actionable messages at profile/compatibility/query/export boundaries.

### 8.5 UI rules
- Optimize for Shan's desktop browser, primarily 1440p/1080p; mobile is not a requirement.
- Every analytical page shows active profile, PFETL run/as-of context, period and material filters.
- Every KPI/chart that can be misunderstood exposes a concise tooltip describing source table/grain/meaning.
- Use tabs/accordions for depth; do not put every metric on the first viewport.
- Heavy data loads are lazy and executed off the NiceGUI event loop.
- Empty, stale, drifted and incompatible states get designed UI, not stack traces.

### 8.6 Read-only and security rules
- Bind NiceGUI to `127.0.0.1` by default.
- DuckDB uses `read_only=True`; Control Plane uses SQLite URI `mode=ro`.
- Check PFETL `pipeline.lock` before opening DuckDB.
- Never write Settings TOML, FinancialRules TOML, PFETL databases or source evidence.
- Retained payload bytes are streamed only after explicit user action.
- Treat database strings/JSONL messages as text; do not render arbitrary HTML.

## 7. Documentation, quality gate and release discipline
### Documentation
The application repository maintains only **one root `README.md`**. No Wiki and no `docs/` directory in v1.

The final product README must cover:
- product purpose and PFETL boundary;
- setup and launch;
- profile inputs;
- architecture diagram;
- page/capability overview;
- prebuilt report catalog;
- read-only guarantee and provenance;
- development/quality commands.

During implementation, this planning package remains external authority. Do not copy phase documents into the product repo.

### Code documentation
- Each package `__init__.py` states what the package owns and does not own.
- Public analytical/report services receive concise docstrings describing input grain, source tables and output grain.
- Comments explain financial/data assumptions only when not obvious from types/names.
- Do not create a documentation maintenance program around the codebase.

### Quality gate
One CI workflow is enough:
```text
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```
No Bandit/Codacy/CodeRabbit/Prospector/flake8 duplication unless a real future problem justifies it.

### Versioning
- Build through `0.x` while phases are in progress.
- Do not tag every phase as a release.
- Cut **`1.0.0` only after Phase 33 acceptance**.
- `1.x` thereafter is compatibility/polish/report growth; financial methodology remains upstream PFETL responsibility.

## 8. Studio-owned state database
Use `platformdirs.user_data_dir("PFETL Analytics Studio")` and a single `studio.sqlite`. Suggested tables:

- `profiles(profile_id, label, settings_path, rules_path, created_at, last_opened_at)`;
- `saved_views(view_id, profile_id, name, page, context_json, spec_json, created_at, updated_at)`;
- `saved_reports(report_id, profile_id, name, description, definition_json, created_at, updated_at)`;
- `report_runs(report_run_id, report_id, pfetl_run_id, period_json, output_format, output_path, generated_at)`.

No authentication, users, roles, migrations framework or audit subsystem. A tiny schema-version integer and additive migration functions are enough.

## 8A. Phase execution authority and construction-spec standard
Every sprint is intentionally small, but **small does not mean underspecified**. For implementation, the agent needs only three things: the current repository source, this README, and the active phase file. Earlier chats, superseded phase drafts and model intuition are not implementation authority.

Every phase file therefore freezes, for that sprint only:

1. the inherited state that may be assumed from earlier phases;
2. exact source and destination files in scope;
3. the PFETL tables/columns or Studio-owned state involved;
4. public models/services/functions that must exist at phase exit;
5. query/aggregation/period semantics and financial non-recomputation rules;
6. concrete UI behaviour, including empty/loading/locked/error states where applicable;
7. ordered implementation steps;
8. deterministic tests and numerical/behavioural assertions;
9. explicit non-goals and stop conditions;
10. mechanical exit criteria and the handoff guaranteed to the next phase.

If repository reality contradicts a phase assumption, **do not silently redesign the product**. Make the smallest source-grounded correction required to satisfy the stated outcome, preserve the README constitution, and record the mismatch in the implementation summary. If the correction would change ownership, financial methodology, read-only safety, the 33-phase product scope, or PFETL upstream contracts, stop and surface the conflict instead of inventing architecture.

### Phase completion rule
A phase is complete only when all of the following are true:

- the requested code is implemented, not stubbed;
- the repository remains runnable;
- focused tests for the phase are green;
- Ruff and mypy remain green for changed code;
- no PFETL file/database/TOML was mutated by Studio tests or runtime;
- no unfinished compatibility alias, TODO implementation or half-migration is left behind;
- the phase exit checklist is mechanically satisfied.

The final implementation should prefer **boring, explicit Python** over frameworks within frameworks. New abstractions are justified only when at least two concrete phase-owned consumers need the same behaviour.

## 9. Upstream data atlas and complete coverage requirement
PFETL v11.3.1 exposes **20 Bronze contracts, 24 Silver tables, 22 Gold tables, 6 Meta tables and 10 Control Plane tables**. Studio must have an explicit consumer path for every one. Bronze is not used for headline finance analytics, but it remains available through Evidence/Data Explorer because its schema is dynamic and source-oriented.
### 9.1 Bronze contracts — all 20
| Extraction | Sync category | Physical table | Studio use |
|---|---|---|---|
| `household_zcategory` | `sqlite_source` | `bronze.household_zcategory` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `household_asset_group` | `sqlite_source` | `bronze.household_asset_group` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `household_assets` | `sqlite_source` | `bronze.household_assets` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `household_currency` | `sqlite_source` | `bronze.household_currency` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `household_inoutcome` | `sqlite_source` | `bronze.household_inoutcome` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `column_master` | `column_master` | `bronze.column_master` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `mutual_fund_instrument_mapping` | `mutual_fund_instrument_mapping` | `bronze.mutual_fund_instrument_mapping` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `instrument_master` | `instrument_master` | `bronze.instrument_master` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `opening_balances` | `opening_balances` | `bronze.opening_balances` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `benchmark_master` | `benchmark_master` | `bronze.benchmark_master` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `financial_year_parameters` | `financial_year_parameters` | `bronze.financial_year_parameters` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `currency_reference` | `currency_reference` | `bronze.currency_reference` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `mf_market_data` | `mf_holdings` | `bronze.mf_market_data` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `mf_transactions` | `mf_orders` | `bronze.mf_transactions` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `stock_market_data` | `stock_pl` | `bronze.stock_market_data` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `stock_transactions` | `stock_orders` | `bronze.stock_transactions` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `us_stock_transactions` | `us_stock_transactions` | `bronze.us_stock_transactions` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `currency_fx_rates` | `currency_history` | `bronze.currency_fx_rates` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `benchmark_history` | `benchmark_history` | `bronze.benchmark_history` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |
| `us_stock_prices` | `us_stock_market` | `bronze.us_stock_prices` | Data Catalog / Evidence Explorer / bounded raw preview; never headline KPI computation |

### 9.2 Silver — canonical drill-down and analytical facts
| Table | Grain / role | Studio use | Key columns available |
|---|---|---|---|
| `silver.dim_calendar` (64) | Common / Day | **Shared filters:** Authoritative day/month/quarter/FY flags and period semantics | `Date`, `Day`, `Day_Name`, `Day_Name_Short`, `Day_Ordinal`, `Day_Ordinal_Name`, `Weekday`, `IS_WEEKEND`, `Week`, `Week_Ordinal`, `Week_Ordinal_Name`, `Week_Name`, `Week_Year`, `Week_Name_Year`, … (+50) |
| `silver.dim_income_category` (3) | Wealth / Category | **Household drill:** Income category labels | `UID`, `CATEGORY_NAME`, `CATEGORY_NAME_SHORT` |
| `silver.dim_income_subcategory` (15) | Wealth / Subcategory | **Household / Tax drill:** Income classification, active/passive flags and tax mappings | `UID`, `CATEGORY_ID`, `CATEGORY_NAME`, `CATEGORY_GROUPS`, `Is_Active_Income`, `Is_Passive_Income`, `Is_Dividend_Income`, `Is_Interest_Income`, `Is_Non_Cash_Income`, `Is_Investment_Exclusion`, `Is_Tax_Credits`, `Tax_Income_Head`, `Tax_Sub_Head`, `Taxability`, … (+1) |
| `silver.dim_expense_category` (2) | Wealth / Category | **Household drill:** Expense category labels | `UID`, `CATEGORY_NAME` |
| `silver.dim_expense_subcategory` (4) | Wealth / Subcategory | **Household drill:** Expense subcategory and core-expense flag | `UID`, `CATEGORY_ID`, `CATEGORY_NAME`, `Is_Core_Expense` |
| `silver.dim_asset_category` (9) | Wealth / Category | **Wealth / Cashflow drill:** Asset group, ledger role, activity, cash-pool/non-cash classification | `UID`, `ASSET_GROUP`, `TYPE`, `ledger_role`, `cashflow_activity_type`, `settlement_timing`, `Is_Digital_Asset`, `is_cash_pool`, `is_non_cash_pnl` |
| `silver.dim_asset_subcategory` (14) | Wealth / Subcategory | **Wealth / transaction drill:** Account/asset detail, liquidity and settlement attributes | `UID`, `ASSET_GROUP_ID`, `CURRENCY_ID`, `ASSET_NAME`, `ASSET_DESCRIPTION`, `NOTES`, `ledger_role`, `cashflow_activity_type`, `settlement_timing`, `Is_Liquid`, `Is_Illiquid`, `Is_Digital_Asset`, `is_cash_pool`, `is_non_cash_pnl` |
| `silver.dim_currency` (7) | Common / Currency | **Investment/FX filters:** Currency names, symbols and market tickers | `UID`, `CURRENCY_NAME`, `ISO`, `Target_Currency_Code`, `yF_Ticker`, `SYMBOL`, `Is_Active` |
| `silver.fact_currency_fx_rates` (13) | Common / Date-Currency | **FX explorer:** Historical FX rate evidence and imputation/gap provenance | `Date`, `Currency_ID`, `Currency_Code`, `Target_Currency_Code`, `yF_Ticker`, `FX_Rate`, `Data_Provider`, `Extraction_Time`, `Requested_Start`, `Requested_End`, `Is_Closure_Gap`, `Is_Imputed`, `First_Observation_Date` |
| `silver.fact_income_transactions` (19) | Wealth / Transaction | **Transaction explorer:** Canonical income transactions and account/local/base values | `UID`, `DATE`, `ASSET_ID`, `CATEGORY_ID`, `CURRENCY_ID`, `TO_ASSET_ID`, `TRANSFER_UID`, `TIME`, `DESCRIPTION`, `PAID`, `TRANSACTION_TYPE`, `Is_Active_Income`, `Is_Dividend_Income`, `Is_Interest_Income`, … (+5) |
| `silver.fact_expense_transactions` (16) | Wealth / Transaction | **Transaction explorer:** Canonical expense transactions and core-expense detail | `UID`, `DATE`, `ASSET_ID`, `CATEGORY_ID`, `CURRENCY_ID`, `TO_ASSET_ID`, `TRANSFER_UID`, `TIME`, `DESCRIPTION`, `PAID`, `TRANSACTION_TYPE`, `Is_Core_Expense`, `BASE_AMOUNT`, `AMOUNT_ACCOUNT`, … (+2) |
| `silver.fact_transfer_transactions` (18) | Wealth / Transaction | **Cashflow drill:** Transfers, analysis-adjusted dates and activity classification | `UID`, `DATE`, `ADJUSTED_DATE_FOR_ANALYSIS`, `ASSET_ID`, `TO_ASSET_ID`, `CATEGORY_ID`, `CURRENCY_ID`, `TRANSFER_UID`, `TIME`, `DESCRIPTION`, `PAID`, `TRANSACTION_TYPE`, `TRANSFER_TYPE`, `BASE_AMOUNT`, … (+4) |
| `silver.fact_opening_balances` (4) | Wealth / Balance | **Wealth reconciliation:** Opening account balances feeding wealth state | `ZASSETUID`, `ZAMOUNTACCOUNT`, `ZTXDATESTR`, `ZUTIME` |
| `silver.dim_benchmark_master` (4) | Investments / Benchmark | **Investment context:** Benchmark labels, currencies and market tickers | `ID`, `CURRENCY_ID`, `Benchmark_Name`, `yF_Ticker` |
| `silver.dim_instrument_master` (17) | Investments / ISIN | **Investment filters:** Instrument master: class/type/subtype/sector/industry/country/geo/tax mapping | `ISIN`, `CATEGORY_ID`, `BENCHMARK_ID`, `CURRENCY_ID`, `INSTRUMENT_NAME`, `INSTRUMENT_HOUSE`, `INSTRUMENT_CLASS`, `INSTRUMENT_TYPE`, `INSTRUMENT_SUBTYPE`, `SECTOR`, `INDUSTRY`, `COUNTRY`, `GEO`, `GEO_SUBTYPE`, … (+3) |
| `silver.ref_financial_year_parameters` (23) | Investments / FinancialYear | **Assumptions / Tax context:** FY-specific inflation, risk-free and tax parameters | `FY`, `FY_Start_Date`, `FY_End_Date`, `Debt_MF_Cutoff_Date`, `Inflation_Rate`, `Risk_Free_Rate`, `Equity_Listed_LTCG`, `Equity_Listed_STCG`, `Equity_Unlisted_LTCG`, `Equity_Unlisted_STCG`, `Equity_LTCG_Exemption`, `Gold_LTCG`, `Gold_STCG`, `Debt_MF_Pre_Cutoff_LTCG`, … (+9) |
| `silver.fact_investment_market_data` (22) | Investments / Quote | **Investment history:** Holdings/valuation history with local/base and provider provenance | `Date`, `ISIN`, `CURRENCY_ID`, `__file_category__`, `Quantity`, `Closing_Price`, `Buy_Price`, `Closing_Value`, `Buy_Value`, `Closing_Price_Local`, `Buy_Price_Local`, `Closing_Value_Local`, `Buy_Value_Local`, `FX_Rate`, … (+8) |
| `silver.fact_investment_purchases` (11) | Investments / Trade | **Lot drill:** Canonical purchase trades and FX/local values | `Purchase_ID`, `Date`, `ISIN`, `CURRENCY_ID`, `__file_category__`, `Quantity`, `Price`, `Value`, `Price_Local`, `Value_Local`, `FX_Rate` |
| `silver.fact_investment_sales` (17) | Investments / Trade | **Realized drill:** Canonical sales and reference P&L fields | `Sale_ID`, `Date`, `ISIN`, `CURRENCY_ID`, `__file_category__`, `Quantity`, `Sell_Price`, `Sell_Value`, `Buy_Price`, `Buy_Value`, `Sell_Price_Local`, `Sell_Value_Local`, `Buy_Price_Local`, `Buy_Value_Local`, … (+3) |
| `silver.fact_investment_benchmark_data` (12) | Investments / Quote | **Benchmark explorer:** Historical benchmark observations and gap/imputation provenance | `Date`, `ID`, `CURRENCY_ID`, `Benchmark_Name`, `yF_Ticker`, `Close`, `Data_Provider`, `Extraction_Time`, `Requested_Start`, `Requested_End`, `Is_Closure_Gap`, `Is_Imputed` |
| `silver.fact_investment_lot_analytics` (88) | Investments / ISIN-Lot | **Lot Lab:** 88-column open-lot accounting/performance/tax/benchmark/FX surface | `Lot_ID`, `Closing_Date`, `ISIN`, `CURRENCY_ID`, `Buy_Date`, `Purchase_ID`, `Lot_Source_Type`, `BENCHMARK_ID`, `TAX_TYPE`, `TAX_SUBTYPE`, `Quantity`, `Execution_Residual`, `Buy_Price`, `Market_Price`, … (+74) |
| `silver.fact_investment_realized_events` (24) | Investments / RealizedEvent | **Realized Lab:** FIFO disposal events, cost basis, local/base/FX P&L and estimated tax | `Realized_Event_ID`, `Sale_ID`, `Lot_ID`, `Purchase_ID`, `ISIN`, `Acquisition_Date`, `Disposal_Date`, `FY`, `Quantity_Disposed`, `Acquisition_Price`, `Disposed_Cost_Basis`, `Sale_Price`, `Sale_Proceeds`, `Realized_Gain_Loss`, … (+10) |
| `silver.fact_investment_reconciliation_events` (17) | Investments / ReconEvent | **Reconciliation Lab:** Broker vs reconstructed quantity/cost-basis adjustments | `Reconciliation_Group_ID`, `Reconciliation_Event_ID`, `Run_ID`, `ISIN`, `Reconciliation_Date`, `Lot_ID`, `Purchase_ID`, `Adjustment_Type`, `Reason`, `Broker_Quantity`, `Reconstructed_Quantity`, `Quantity_Adjustment`, `Broker_Cost_Basis`, `Reconstructed_Cost_Basis`, … (+3) |
| `silver.fact_tax_events` (15) | Taxes / TaxEvent | **Tax drill:** Canonical ledger + investment tax events and readiness status | `Tax_Event_ID`, `FY`, `Event_Date`, `Source_Type`, `Source_ID`, `Income_Head`, `Tax_Sub_Head`, `Amount_INR`, `Applied_Rate`, `Estimated_Tax`, `CURRENCY_ID`, `Tax_Status`, `Tax_Status_Reason`, `ISIN`, … (+1) |

### 9.3 Gold — every presentation/analytics mart
| Table | Studio page | Purpose | Primary filters |
|---|---|---|---|
| `gold.tax_financial_year_summary` (17 cols) | **Tax** | FY tax cockpit, completeness, realized/unrealized exposure | FY; compare FY; source completeness |
| `gold.tax_income_breakdown` (11 cols) | **Tax** | Income-head and sub-head tax decomposition | FY; income head; sub-head; source type |
| `gold.tax_reconciliation` (22 cols) | **Tax** | Ledger-vs-quant tax reconciliation and exclusions | FY; sub-head; discrepancy status |
| `gold.wealth_asset_breakdown` (33 cols) | **Wealth** | Asset-level monthly balances, liquidity, drawdown, flows and runway | Period; asset; liquidity; cash/non-cash |
| `gold.core_monthly_fact` (45 cols) | **Overview / Wealth** | Canonical monthly financial cockpit and net-worth attribution | Month/FY/custom range; period comparison |
| `gold.cashflow_expense_breakdown` (15 cols) | **Household** | Expense category trends, core/discretionary/investment spend | Period; category; group; spend type; core flag |
| `gold.cashflow_income_breakdown` (14 cols) | **Household** | Income streams and active/passive/dividend/interest decomposition | Period; category; group; income flags |
| `gold.wealth_fire_analytics` (35 cols) | **FIRE** | FI targets, probabilities, runway, wealth velocity and required savings | Period; scenario/context; selected run/simulation |
| `gold.forecast_budget_variance` (27 cols) | **Household** | Budget vs actual, overspend, investment funding and runway | Period; health flags; budget target |
| `gold.investment_portfolio_summary` (32 cols) | **Investments** | Month-ISIN allocation, performance, drift, harvesting priority | Period; ISIN; class; type; subtype; sector; currency |
| `gold.cashflow_efficiency_analytics` (47 cols) | **Overview / Household** | Savings/investment efficiency, income mix, liquidity, debt and resilience | Period; comparison window |
| `gold.investment_by_isin` (46 cols) | **Investments** | Deep ISIN performance, tax, benchmark and FX metrics | Date; ISIN; currency |
| `gold.investment_by_subtype` (23 cols) | **Investments** | Allocation/performance by instrument subtype | Date; subtype; class |
| `gold.investment_by_class` (22 cols) | **Investments** | Allocation/performance by asset class | Date; class |
| `gold.investment_by_instrument_type` (22 cols) | **Investments** | Allocation/performance by instrument type | Date; instrument type |
| `gold.investment_by_sector` (22 cols) | **Investments** | Sector allocation/performance | Date; sector |
| `gold.investment_by_industry` (22 cols) | **Investments** | Industry allocation/performance | Date; industry |
| `gold.investment_by_portfolio` (31 cols) | **Investments** | Whole-portfolio return, concentration and LTCG maturity ladder | Date |
| `gold.investment_by_geo` (22 cols) | **Investments** | Geographic allocation/performance | Date; geography |
| `gold.investment_by_country` (31 cols) | **Investments** | Country allocation with local/base and FX decomposition | Date; country |
| `gold.investment_by_currency` (31 cols) | **Investments** | Currency exposure with local/base return decomposition | Date; currency |
| `gold.cashflow_activity_summary` (24 cols) | **Household** | Operating/investing/financing cashflow statement and reconciliation | Period; activity type |

### 9.4 Meta — latest warehouse context
| Table | Studio use |
|---|---|
| `meta.m_File_Registry` (10 cols) | Latest warehouse-side artifact registry and Bronze row counts |
| `meta.m_Table_Row_Counts` (4 cols) | Latest Silver/Gold table row counts and generation timestamp |
| `meta.m_Financial_Rules` (4 cols) | Flattened latest FinancialRules audit projection |
| `meta.m_Settings` (3 cols) | Flattened latest Settings audit projection |
| `meta.m_Data_Contracts` (8 cols) | Runtime contract catalog: layer, grain, producer and publication order |
| `meta.m_Latest_Simulation` (15 cols) | Latest simulation fingerprints, seed, horizon, snapshots and model version |

### 9.5 Control Plane — historical operational truth
| Table | Studio use |
|---|---|
| `cp_file_registry` (16 cols) | Current source artifact state, hashes, size, first/last seen/changed/synced history |
| `cp_file_payloads` (2 cols) | Retained raw evidence bytes; on-demand evidence download only |
| `cp_settings_snapshots` (4 cols) | Immutable effective Settings snapshots used by runs |
| `cp_rules_snapshots` (4 cols) | Immutable effective FinancialRules snapshots used by runs |
| `cp_runs` (10 cols) | Run history, commit state, Core/schema version, snapshot IDs and compressed JSONL trace |
| `cp_run_failures` (9 cols) | Failure stage/type/domain/message/traceback and failed ISIN |
| `cp_artifact_run_events` (14 cols) | Source change timeline, rename/replay/convergence and affected-table lineage |
| `cp_external_provider_requests` (11 cols) | Provider/entity/request window, attempts, status and failure details |
| `cp_run_sync_summaries` (8 cols) | Per-run actionable/synced/healed/failed/deferred ingestion summary |
| `cp_simulation_runs` (14 cols) | Simulation history, seed, horizon and reproducibility fingerprints |
### Coverage gate
Add a test which discovers current PFETL tables and fails if a Bronze/Silver/Gold/Meta contract or Control Plane table has no Studio classification. This is the mechanical protection against “we forgot a table”. New columns may appear without breaking Studio; new datasets must be deliberately classified.
## 10. Time and comparison model
Use `silver.dim_calendar` for calendar/FY semantics instead of reproducing date rules. Every financial page/report accepts a `PeriodContext` with:

- latest complete month; selected month; previous month;
- calendar quarter; FY quarter;
- calendar YTD; FYTD; selected financial year;
- rolling 3 / 6 / 12 / 24 months;
- since inception;
- custom start/end date.

Comparison modes:

- previous equivalent period;
- same period previous year;
- selected comparison period;
- no comparison.

Investment views additionally support latest available closing date within the selected period. Tax defaults to financial year. Operations uses run-date windows rather than financial periods.
## 11. Global and domain filters
Shared filters are explicit, not a generic arbitrary-query framework.

**Household / wealth:** asset group, asset/account, income category/subcategory/group, expense category/subcategory/group, core/non-core, cash/non-cash, active/passive, cashflow activity, liquidity.

**Investments:** ISIN, instrument name, class, type, subtype, sector, industry, country, geography, geography subtype, currency, benchmark, tax type/subtype.

**Tax:** FY, income head, tax sub-head, source type, tax status, ISIN, lot.

**Operations:** run ID/status/commit state/Core version, source category/status, event type, provider, request status, failure domain/stage/error type, observability severity/stage/component/operation/event code/entity/provider/cache-hit/worker/batch.
## 12. Application navigation and personalized pages
Use a persistent left navigation plus profile/run context header:

`Overview | Household | Wealth | Investments | Tax | FIRE | Operations | Explorer | Reports`

The header always shows: profile label, selected Settings/Rules filenames, latest successful PFETL run, Core version, warehouse as-of state, profile drift badge and a Data Health badge.
### 12.1 Overview — monthly cockpit
Use `gold.core_monthly_fact`, `gold.cashflow_efficiency_analytics`, `gold.investment_by_portfolio`, `gold.wealth_fire_analytics`, tax summary and latest operational freshness. Include:

- net worth / market net worth, monthly and YoY movement;
- net-worth attribution bridge: net savings + market return + residual;
- income, expense, core expense, net cashflow, savings rate, investment rate;
- passive-income coverage, active-income dependency, liquidity/runway;
- portfolio current value, XIRR, benchmark XIRR, active return, asset P&L, FX P&L;
- concentration (Top1/5/10, HHI, effective holdings);
- indicative tax exposure;
- FI coverage, target gap, P50 date, success probability;
- freshness: last successful run, latest household transaction, investment close, benchmark and FX dates.
### 12.2 Household
Income: trends, active/passive/dividend/interest mix, category/subcategory drill, 3M averages, YTD/FYTD cumulative income, income resilience.

Expenses: core/non-core, discretionary/investment/fixed grouping, category contribution, trailing spend, real core-expense growth, lifestyle inflation, transaction drill.

Budget: actual vs configured budget targets, overspend flags, investment funding, surplus buffer, emergency-fund gap, zero-income runway.

Cashflow statement: operating/investing/financing inflow/outflow/net, internal transfers, cash vs non-cash, unreconciled difference.
### 12.3 Wealth
Net-worth timeline, book vs market balances, asset-level opening/closing balances, liquid assets, liabilities, drawdown from peak, organic growth/yield, cumulative net savings, asset P&L vs FX P&L, runway, savings-to-net-worth ratio and investment contribution. Drill asset → canonical transactions.
### 12.4 Investments
Portfolio Overview: value/book value, return, XIRR, after-tax XIRR, benchmark, active return, asset/FX decomposition.

Allocation: class/type/subtype/sector/industry/country/geo/currency/instrument with weight, value and P&L.

Performance: ISIN and group return histories, benchmark comparison, max drawdown, outperforming-lot ratio, FX XIRR impact.

Concentration: Top1/5/10, HHI, effective holdings, largest contributors.

Lot Lab: all 88 lot columns grouped into Identity, Cost/Value, FX, Performance, Benchmark/Alpha, Risk, Weight, Holding/Tax, Realized FY, Harvesting.

Realized Lab: sale → FIFO lot matches, proceeds, disposed basis, local/base asset P&L, FX P&L, holding type, rate and estimated tax.

Reconciliation Lab: broker vs reconstructed quantity/basis and each adjustment event.

Market Evidence: holdings/quotes, benchmarks and FX observations with provider/gap/imputation flags.
### 12.5 Tax
FY summary, income-head/sub-head decomposition, estimate completeness, ledger-vs-quant reconciliation, tax credits/exclusions, realized investment tax, unrealized tax-if-sold, harvestable loss/savings, net indicative exposure and direct drill to canonical tax events / lots. Always label tax figures **Indicative / estimated, not statutory liability**.
### 12.6 FIRE / Planning
FI target/Coast/Lean values, gap, coverage, wealth velocity/acceleration, real NW CAGR, P10/P50/P90 months to FI, success probability, runway, withdrawal rate, actual vs required savings rate, simulation provenance and history.

Presentation-only sensitivity controls may show “what if savings/expenses/return/inflation changed”, but must be labelled **Scenario only — not PFETL canonical output** and never written back. Initial implementation may limit scenarios to arithmetic sensitivities over canonical outputs; do not reproduce the Monte Carlo engine.
### 12.7 Operations / Data Health / Forensics
This page consumes all Control Plane + Meta surfaces:

- run timeline: status, commit state, duration, Core/schema version, snapshots and log availability;
- sync health: actionable/synced/healed/failed/deferred;
- source freshness: first/last seen/changed/synced, hash/size/category/status;
- artifact event timeline: added/changed/removed/renamed/replayed/converged and affected table;
- provider requests: provider/entity/window/attempts/status/failure;
- failures: domain/stage/type/message/failed ISIN and traceback;
- simulation history and reproducibility fingerprints;
- data catalog + current row counts;
- Settings/Rules run-to-run diff;
- archived JSONL forensic event browser;
- evidence payload availability and on-demand source download from `cp_file_payloads`.
### Forensic event analytics
Decompress `cp_runs.execution_log` and parse each line as the existing `ObservabilityEvent`. Support filters for timestamp, severity, event code, outcome, presentation kind, run/stage/component/operation, parent/operation IDs, entity, duration, rows, attempt, provider, cache hit, worker, batch, commit state, settings/rules fingerprints and structured error fields. Build:

- chronological run timeline;
- stage/component duration summaries where `duration_ms` is present;
- slowest operations;
- processed-row summaries;
- retry/provider/cache-hit summaries;
- worker/batch activity;
- failure-domain/error breakdown;
- operation parent-child lineage tree;
- raw JSON detail drawer.
## 13. Explorer — exhaustive access without turning Studio into a BI platform
The Explorer has three modes:

1. **Data Catalog** — every Bronze/Silver/Gold/Meta table, contract grain/producer, columns, row count and bounded preview.
2. **Guided Analytics** — choose an approved dataset, dimensions, registered metrics, filters, sort and chart. Only metrics with known safe aggregation are offered.
3. **Advanced SQL** — optional read-only SELECT/WITH queries against either DuckDB or Control Plane, with row limit and query timeout. The database itself is read-only; no SQL write capability is required.

Saved views persist the page/query spec and filters in Studio SQLite. Do not persist query result copies.
## 14. Semantic registry — safe custom analytics
Do not infer that every numeric column is additive. Maintain a compact `MetricSpec` registry for reusable measures with:

- display name; source dataset/expression; aggregation (`sum`, `avg`, `latest`, `weighted`, `none`); format; unit; description; allowed dimensions; additive flag.

Examples: current value → `sum`; XIRR → `none/latest` at its native grain; portfolio weight → `none` unless query explicitly recomputes from values; tax estimate → `sum` only at compatible event grain.

The raw Explorer can still display every column. The Guided Analytics and Report Builder expose only registered metrics, preventing mathematically meaningless custom reports.
## 15. Report period and filter framework
Every built-in and custom report carries one `ReportContext`:

- profile ID; PFETL run ID/as-of run mode;
- period preset or custom start/end;
- optional comparison mode;
- domain filters;
- report currency presentation mode where already available (base/local; no new conversion methodology).

Every exported report includes a provenance footer/cover block with Core version, PFETL run ID, data as-of period, Settings snapshot ID, Rules snapshot ID, Studio version, generation timestamp and an “Indicative tax” disclaimer where relevant.
## 16. Prebuilt report catalog
| Report | Default timeline | Supported filters | Key content |
|---|---|---|---|
| **Monthly Financial Review** | Latest complete month | Month; account/asset; optional comparison | Net worth, attribution, income, expense, cashflow, portfolio, tax, FIRE, data health |
| **Financial Year Review** | Selected FY | FY; asset; income/expense groups; investments | FY income/expense/savings, wealth change, investments, realized gains/tax, FIRE progress |
| **Net Worth & Wealth Attribution** | Rolling 12M | Custom period; asset/liquidity | Book/market NW, assets/liabilities, attribution, P&L/FX, drawdown, runway |
| **Cashflow & Budget Review** | Selected month / FYTD | Period; category; cashflow activity | Operating/investing/financing cashflow, savings/investment rate, budget variance, runway |
| **Expense & Lifestyle Review** | Rolling 12M | Period; category/group; core flag | Core/non-core, real growth, category changes, trailing spend, transaction appendix |
| **Income Resilience Review** | Rolling 12M | Period; income category/group | Active/passive mix, coverage, dependency, trend and source drill |
| **Portfolio Review** | Latest close / custom period | Class/type/subtype/sector/country/geo/currency | Value, allocation, XIRR, benchmark, FX, concentration, drift |
| **Investment Performance & Benchmark** | Custom period | ISIN/group dimensions | CAGR/XIRR, benchmark, alpha/active return, drawdown, FX impact |
| **Investment Tax & Harvesting** | Selected FY / latest close | ISIN; tax type; holding type | Realized events, tax if sold, losses, harvesting, LTCG maturity ladder |
| **Tax Position Review** | Selected FY | Head/sub-head/source/status | Income tax evidence, completeness, reconciliation, credits, indicative exposure |
| **FIRE & Planning Review** | Latest month | Custom comparison only | FI targets/gap, P10/P50/P90, success probability, savings required, simulation provenance |
| **Data Health & PFETL Operations** | Last 10 runs / custom run window | Run/source/provider/status | run health, sync, artifacts, providers, failures, row counts, freshness |
| **Run Forensic Report** | Selected run | stage/component/severity | event timeline, slow operations, failures, lineage, config/rules snapshots |
| **Source Evidence & Change Report** | Custom run/date window | source category/file/event | artifact history, hashes, changes, replay/convergence and retained payload availability |
| **Multi-Currency Exposure Review** | Latest close / custom period | currency/country/ISIN | base/local values, FX rates, appreciation, asset P&L vs FX P&L, FX XIRR impact |

All reports support PDF. Table-heavy reports also support XLSX. Any individual table supports CSV. Any Plotly figure supports PNG/SVG export.
## 17. Custom report builder
A custom report is an ordered list of blocks stored as JSON in Studio SQLite. Block types:

- title / subtitle / narrative;
- provenance / assumptions block;
- KPI group;
- registered chart;
- registered table;
- saved-view block;
- page break / section divider.

Workflow:

1. choose global report period + filters;
2. add blocks from the prebuilt analytical registry or saved views;
3. optionally override block-specific filters;
4. reorder blocks;
5. preview;
6. save / duplicate / rename;
7. export PDF/XLSX;
8. regenerate later against a newer PFETL run while preserving the same definition.

Built-in reports are immutable templates but can be **Clone to Custom**. No arbitrary formula DSL in v1. Advanced SQL results may be added as table blocks only after saved-view validation.
## 18. Export architecture
**PDF:** query → Plotly figure → Kaleido image → ReportLab page composition. Never screenshot the web UI.

**XLSX:** XlsxWriter workbook with summary sheet, domain sheets, provenance sheet, formatted tables and embedded chart images.

**CSV:** direct Polars export of the visible/query table.

**PNG/SVG:** Plotly static export through Kaleido.

Generated files default to a user-selected output directory; Studio records only the output path/history in its own database. Do not save generated reports into PFETL storage automatically.
## 19. Theme — deliberately match PFETL Core
Use the existing Core palette as the initial Studio design tokens:

```text
BG       #0D1117
SIDEBAR  #101624
BORDER   #1E293B
ACCENT   #3B82F6
ACC_HOV  #2563EB
SUCCESS  #22C55E
WARNING  #F59E0B
ERROR    #EF4444
RECOVERY #C084FC
TEXT     #E2E8F0
LOG_BG   #080C14
```

Studio may add chart-series colors, but preserve the same status semantics. Do not create a shared cross-repo theme package for a handful of constants.
## 20. Query/cache/performance rules
- Push filtering/grouping into DuckDB SQL; use Polars mainly for final shaping/export.
- Open short-lived read-only DB connections per background query rather than sharing one busy connection across UI callbacks.
- Run blocking queries outside the NiceGUI event loop (`run.io_bound`/thread helper).
- Cache results by `(profile_id, latest_successful_run_id, query_name, normalized_filters)`. A new successful PFETL run invalidates the profile cache automatically.
- Never create a second analytical warehouse or persisted query-result cache.
- Apply default row limits to raw Explorer and Advanced SQL.
- Lazy-load heavy tables (lot analytics, event logs, payload bytes) only when opened.
## 21. Data-health rules shown throughout Studio
Do not invent a magic 0–100 trust score. Show explicit conditions:

- latest run status/commit state;
- profile drift;
- source sync failures/deferred artifacts;
- provider request failures;
- tax estimate completeness flags;
- cashflow `Unreconciled_Difference`;
- investment reconciliation event count/adjustment magnitude;
- latest transaction / investment / benchmark / FX dates;
- row-count availability and simulation provenance.

Reports may render a concise “Data Health” section containing these facts.
## 22. Testing strategy
Tests are capability-oriented, never phase-oriented. The finished suite should remain small enough that Shan understands why every test exists.

1. `test_profile_connections.py`
   - resolve Settings/Rules profile;
   - open DuckDB/Control Plane read-only;
   - refuse DuckDB while `pipeline.lock` is active;
   - compare current TOMLs with latest run snapshots.
2. `test_catalog_compatibility.py`
   - discover 20 Bronze, 24 Silver, 22 Gold, 6 Meta and 10 Control Plane surfaces;
   - validate required columns/grains;
   - fail compatibility cleanly when required upstream contracts disappear.
3. `test_semantic_queries.py`
   - deterministic household/wealth/tax/FIRE fixture results;
   - period boundaries, FY/FYTD/YTD/rolling/custom periods and comparison math.
4. `test_investment_queries.py`
   - allocation/performance/concentration queries;
   - lot, realized and reconciliation drill relationships;
   - no invalid aggregation of XIRR/CAGR/weights.
5. `test_operations_forensics.py`
   - run/sync/artifact/provider/failure/simulation history;
   - zlib `cp_runs.execution_log` decode and JSONL lineage parsing;
   - retained-payload metadata without eager BLOB loading.
6. `test_explorer.py`
   - guided query whitelist;
   - saved-view round trip;
   - advanced SQL rejects writes/multiple statements and enforces row limits.
7. `test_reports.py`
   - representative household, investment and operations built-ins;
   - one custom report;
   - provenance stamp;
   - PDF/XLSX/CSV/chart exports.
8. `test_smoke.py`
   - app shell and all nine pages construct against fixtures;
   - empty/drifted/incompatible states render without exceptions.

### Golden-fixture rule
Use one tiny deterministic PFETL-like DuckDB/Control Plane fixture with expected numbers checked into `tests/fixtures/expected/`. Do not copy Shan's private production finance data into the repository.

### Coverage gate
A dedicated assertion must classify **every** upstream PFETL contract/table. A new PFETL surface must be deliberately marked `ANALYTICAL`, `DRILL`, `OPERATIONS`, `EVIDENCE`, or `NOT_USED_WITH_REASON`; silent omission is a test failure.

## 23. Phase map — 33 authoritative 2–3 hour sprints

Every phase is an independently completable **2–3 focused hour** sprint. The phase ends only when its focused tests/verification are green and the repository is runnable. If implementation reveals genuinely larger work, do not silently widen the phase; keep the architecture and split only the concrete unforeseen remainder.

| Phase | Scope | Exit result |
|---:|---|---|
| 01 | **Repository bootstrap and quality baseline** | Installable repo, locked environment, quality gate, `pfetl-studio` skeleton |
| 02 | **PFETL profile resolution and Studio state** | Settings/Rules pair resolves paths, recent profiles persist, no PFETL writes |
| 03 | **Read-only DuckDB and Control Plane gateways** | Lock-safe read-only DB access and bounded query primitives |
| 04 | **Catalog, compatibility, provenance and archived-log spine** | Full upstream catalog, compatibility screen, run snapshots/drift and zlib JSONL parsing |
| 05 | **Semantic periods, filters, metrics and cache** | Reusable safe period/filter/metric semantics and run-keyed query cache |
| 06 | **NiceGUI shell, theme, navigation and global context** | Nine-page shell with PFETL theme/profile/run/period context |
| 07 | **Overview cockpit** | Monthly decision cockpit with drill links and data-health strip |
| 08 | **Household income analytics** | Income trend/mix/resilience/category drill and transactions |
| 09 | **Household expense analytics** | Core/non-core/lifestyle/inflation/category trends and transaction drill |
| 10 | **Budget and cashflow analytics** | Budget variance, operating/investing/financing cashflow and reconciliation |
| 11 | **Household transaction and classification explorer** | Unified household drill to canonical facts/dimensions with exports |
| 12 | **Wealth, net worth, liquidity and attribution** | Balance sheet, asset drill, runway, drawdown and net-worth attribution |
| 13 | **Investment overview and allocation** | Portfolio state and every Gold allocation lens |
| 14 | **Investment performance, benchmark, FX and concentration** | Return/benchmark/FX/risk/concentration analytics |
| 15 | **Investment lot explorer** | All lot-analytics sections with filtering and traceable IDs |
| 16 | **Realized events, reconciliation and market evidence** | FIFO disposal drill, reconciliation groups and quote/FX evidence |
| 17 | **Tax analytics** | FY/head/sub-head/reconciliation/exposure/harvesting with rules provenance |
| 18 | **FIRE and simulation analytics** | FI metrics, trajectories, simulation history/provenance and labelled sensitivity |
| 19 | **Operations run history and sync health** | Runs, sync summaries, warehouse/meta freshness and row counts |
| 20 | **Artifact, provider, failure and snapshot intelligence** | File/change/provider/failure/config/rules/simulation operational analysis |
| 21 | **Forensic JSONL and retained source evidence** | Event lineage, slow operations, errors/workers/cache plus explicit payload download |
| 22 | **Data catalog and guided explorer** | Every Bronze/Silver/Gold/Meta table browsable with safe guided analytics |
| 23 | **Saved views and advanced read-only SQL** | Reusable views plus guarded expert SELECT/WITH workspace |
| 24 | **Report definition, provenance and rendering runtime** | Report block model, run context, preview pipeline and report history |
| 25 | **PDF, XLSX, CSV and chart exporters** | Deterministic multi-format export system with provenance |
| 26 | **Prebuilt monthly, FY and wealth reports** | Monthly Financial, FY Review, Net Worth & Wealth Attribution |
| 27 | **Prebuilt cashflow, expense and income reports** | Cashflow & Budget, Expense & Lifestyle, Income Resilience |
| 28 | **Prebuilt portfolio, performance and multi-currency reports** | Portfolio, Performance & Benchmark, Multi-Currency Exposure |
| 29 | **Prebuilt tax, harvesting and FIRE reports** | Investment Tax & Harvesting, Tax Position Review, FIRE & Planning |
| 30 | **Prebuilt operations, forensic and evidence reports** | Data Health & PFETL Operations, Run Forensic, Source Evidence & Change |
| 31 | **Custom report editor and persistence** | Create/clone/edit/reorder/save custom report definitions |
| 32 | **Custom report preview, rerun and export integration** | Preview/rerun custom reports and export through common runtime |
| 33 | **Final hardening, acceptance, README and 1.0.0 freeze** | Real-profile acceptance, performance/polish, concise product README, v1 freeze |

## 24. Final acceptance — Analytics Studio 1.0.0
Analytics Studio is complete only when Shan can, from one local app:

1. select the same Settings TOML + FinancialRules TOML used by PFETL Core and reopen recent profile pairs;
2. resolve DuckDB, Control Plane/Raw Store and logs solely from that profile;
3. see whether selected files match/drift from the latest warehouse-producing run snapshots;
4. browse every Gold analytical surface and drill to Silver evidence without writing SQL;
5. inspect every Bronze/Meta table through bounded evidence/catalog views;
6. use every Control Plane table for run, source, provider, failure, snapshot, simulation or evidence analysis;
7. decode and explore archived JSONL for any run, including event hierarchy, timing, retries, rows, provider/cache, workers and structured errors;
8. analyze household income, expenses, budget, cashflow, wealth and net-worth attribution across standard and custom periods;
9. analyze portfolio allocation, performance, benchmark, FX, concentration, lots, realized events and reconciliation;
10. analyze tax evidence/exposure/harvesting and FIRE/simulation outputs with the exact run's FinancialRules provenance;
11. use guided analytics, saved views and guarded advanced SQL for novel questions;
12. generate all 15 prebuilt reports for their natural/default periods and meaningful custom periods/filters;
13. clone a built-in report, create a custom report, save it, rerun it against a newer PFETL run and export PDF/XLSX;
14. export any visible analytical table to CSV and chart to PNG/SVG;
15. prove every generated report's PFETL run, Core version, schema version, Settings snapshot, Rules snapshot, period, filters and Studio version;
16. use the Studio while PFETL is idle without either application mutating the other's state;
17. receive a designed locked/stale/incompatible state when PFETL is running or schema compatibility is not met;
18. run Ruff, mypy and pytest successfully from a fresh `uv sync --frozen` environment;
19. confirm Studio writes only its own `studio.sqlite` and user-requested report files;
20. use the product README as the only maintained documentation surface.

**Release condition:** only after this checklist is green does the project become `1.0.0`.

## 25. Explicit non-goals
No multi-user/auth, cloud deployment, REST API, microservices, plugin system, generic public BI product, write-back, data editing, source ingestion, duplicate finance engine, AI/LLM in v1, scheduler, background monitoring service, separate warehouse, shared contracts package, Node/React frontend, or native desktop wrapper.
## 26. External stack references checked during planning
Planning-time references were verified on 23 Nov 2026:
- NiceGUI PyPI: https://pypi.org/project/nicegui/
- NiceGUI docs: https://nicegui.io/documentation
- Plotly PyPI: https://pypi.org/project/plotly/
- DuckDB Python/read-only docs: https://duckdb.org/docs/current/clients/python/dbapi
- DuckDB concurrency: https://duckdb.org/docs/current/connect/concurrency
- Polars PyPI: https://pypi.org/project/polars/
- Pydantic PyPI: https://pypi.org/project/pydantic/
- Kaleido PyPI: https://pypi.org/project/kaleido/
- Plotly static export: https://plotly.com/python/static-image-export/
- XlsxWriter PyPI: https://pypi.org/project/XlsxWriter/
- ReportLab PyPI: https://pypi.org/project/reportlab/
