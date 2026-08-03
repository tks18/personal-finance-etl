<div align="center">
  <img src="logo.png" alt="Logo" width="180"/>
  <h1>Shan's Personal Finance Quant Engine 💸✨</h1>
  <p><b>An institutional-grade, hyper-optimized Quantitative Master Engine built to absolutely dominate personal net worth.</b></p>
  <p><i>Because tracking your bags in a spreadsheet in 2026 is pure NPC behavior.</i></p>

  <p>
    <img alt="Python Version" src="https://img.shields.io/badge/Python-3.13+-blue.svg?style=for-the-badge&logo=python&logoColor=white" />
    <img alt="Tech Stack" src="https://img.shields.io/badge/Engine-Polars%20%7C%20DuckDB-FF8C00.svg?style=for-the-badge" />
    <img alt="Type Safety" src="https://img.shields.io/badge/Type%20Safety-Strict%20(100%25)-4C1.svg?style=for-the-badge" />
    <img alt="Architecture" src="https://img.shields.io/badge/Architecture-Event%20Driven%20DAG-8A2BE2.svg?style=for-the-badge" />
  </p>
</div>

---

## 🗣️ The Manifesto (No Cap)

Let's get one thing straight right out of the gate: **this is not a generic, plug-and-play budget tracker.** 

If you want a colorful pie chart that tells you you spend too much on coffee, go download a SaaS app. 

This is a rigorously mathematical, multi-processed **Quantitative Wealth Manager** running natively on bare metal. I built this monolith from scratch to ingest messy broker logs, scattered mutual fund statements, and raw bank transactions, and forge them into a single, aggressively performant `DuckDB` data warehouse.

I'm open-sourcing the engine because gatekeeping institutional architecture patterns is cringe. If you want to see how to build a highly relational, 100% type-safe financial pipeline that calculates true Modified Dietz cashflows, actively hunts tax-alpha, and runs stochastic Monte Carlo survival simulations on your laptop—you have arrived.

*(Disclaimer: My actual portfolio data, net worth, and personal TOML configs are strictly `.gitignore`'d. You won't find my bags here. We stay secure. 🔒)*

---

## 🔥 The Alpha (Institutional Quant Features)

This pipeline doesn't just log where your fiat went. It actively models risk, tests survival, and mathematically optimizes your capital preservation. 

### 🎲 Stochastic FIRE Forecaster (Monte Carlo Survival)
We don't draw a straight, linear line to retirement. The Quant Engine runs thousands of randomized, fat-tailed standard-T distributions across your portfolio.
- **Sequence of Return Risk (SORR):** Actively forces your portfolio through brutal simulated market drawdowns to mathematically prove your probability of success.
- **Stagflation Drift Modeling:** Runs a geometric Brownian motion random walk for inflation, actively widening your future FIRE targets to simulate severe macro shocks over a 360-month horizon.
- **Yield Drag Awareness:** Dynamically haircuts your simulated gross returns based on tax friction to prevent wealth overstatement.

### 🧠 True Cashflow Attribution (Modified Dietz)
Stop conflating your savings rate with your investment acumen. The engine completely isolates investment performance using internal portfolio cashflows (`Inv_Cashflow`), zeroing out the massive distortions caused by global external savings. It knows exactly what you saved vs. what the market actually gave you.

### 🦅 Tax-Alpha Harvesting
The engine dynamically parses your long-term and short-term capital gains rules (`financial_rules.toml`) and actively hunts your open portfolio for loss harvesting opportunities. It ranks them based on the actual fiat currency saved (`Net_Tax_Benefit`), exploiting the arbitrage between holding periods and distinct asset tax rates.

### 🏛️ Institutional Risk Metrics
We eradicate the "Nominal Illusion."
- **Real Drawdowns:** Tracks `Real_Drawdown_Pct` to measure your true purchasing power erosion during high-inflation environments.
- **Dynamic Sharpe & Calmar Ratios:** Maps your portfolio's annualized volatility against a historically accurate, dynamic Risk-Free Rate using temporal `join_asof` operations.
- **Liquid Liability Coverage:** Strips out illiquid assets (like real estate) to mathematically evaluate your immediate solvency risk against your rolling debt.
- **Target-Weighted Benchmarking:** Equal-weight assumptions are gone. The Sector Rotation engine natively understands your specific mandate (e.g., `Direct Stocks`, `ETFs`) and autonomously flags concentration risks.

---

## 🛠️ The Tech Stack (The Ferrari)

- **Core Engine:** `Polars` (Streaming memory graphs for infinite out-of-core scaling)
- **Data Warehouse:** `DuckDB` (Columnar, lightning-fast disk synchronization)
- **Source Extractor:** `SQLite` + `adbc-driver-sqlite` (Zero-copy Arrow memory transfers)
- **Financial Math:** `pyxirr`, `numpy`, `scipy`
- **Control Panel:** `CustomTkinter` (Dark mode only. Peak aesthetics)
- **Configuration:** `Pydantic` strict validation over `TOML`
- **DevOps:** `uv` (Insane dependency resolution) & `PyInstaller`

---

## ⚙️ The Pipeline Architecture

If you're a developer looking under the hood, here is how the monolith is engineered to never crash:

1. **Phase 1 (Gatekeeper Extraction):** Raw CSVs, Excel binaries, and SQLite databases are pulled into memory. The system runs an instant `head(1)` fail-fast Polars evaluation to guarantee schema integrity before wasting a single CPU cycle.
2. **Phase 2 (The Transformation DAG):** A strictly decoupled Directed Acyclic Graph harmonizes currencies, maps hierarchical dimensions, and dedupes all historical state.
3. **Phase 3 (Quant Analytics):** The `InvestmentQuantEngine` takes over. Parallel execution graphs spawn across your CPU cores to compute tax-lots, execute temporal benchmark joins, and run the Monte Carlo batches.
4. **Phase 4 (DuckDB Materialization):** The presentation layer (`p_tf_` tables) is aggressively materialized and flushed directly to the local `DuckDB` columnar file.
5. **True Multiprocessing:** The `CustomTkinter` GUI and the ETL pipeline live in completely isolated OS processes communicating strictly via `QueueHandlers`. The UI never freezes, maintaining peak 60fps telemetry visibility while Polars chews through millions of rows in the background.

---

## 🗄️ The Data Warehouse (Star Schema)

The downstream database is rigorously modeled and entirely BI-ready. No complex DAX required.

### 📊 The Presentation Tier (`p_tf_`)
- **`p_tf_Net_Worth_Monthly_Summary`:** Tracks cumulative running balances, Organic Yields, Asset Velocity, and `Months_of_Runway`.
- **`p_tf_Financial_Ratios_Monthly`:** Tracks structural health like Liquid Liability Coverage, Real Savings Rates, and FIRE progress.
- **`p_tf_FIRE_Forecast_Stochastic`:** The raw output grid of all Monte Carlo wealth paths (10th, 50th, 90th percentiles).
- **`p_tf_Risk_Dashboard`:** Trailing 12M Volatility, Calmar Ratio, Sharpe Ratio, Sortino Ratio, and Effective Diversification indices.

### 🧬 Dimension Mastery (`d_`)
- **`d_Calendar` & `d_Macro_Parameters`:** Flawless date tables spanning from the year 2000, mapped against historical inflation rates and real-time interest rate benchmarks.
- **`d_Income_SubCategory`, `d_Expense_Category`, `d_Asset_SubCategory`:** Strict hierarchical entity groupings.

---

## 🚀 Developer Quickstart

If you want to fork this and adapt the codebase to your own life, here is the playbook:

### 1. Install Dependencies
We use `uv` for lightning-fast package management. Clone the repo and sync:
```bash
uv sync
```

### 2. Configure your Environment
Create your `config.toml` (data paths) and `financial_rules.toml` (tax rates, macro fallback assumptions, target allocations). The GUI automatically remembers your recent environments.

### 3. Run or Build
Custom CLI entry points are registered in `pyproject.toml`:
```bash
# Run the GUI in dev mode with hot-reloading
uv run dev

# Compile a standalone native EXE using PyInstaller
uv run build
```

---

## 💅 The Release Cycle

We run enterprise-grade SDLC here. Semantic versioning is strictly enforced via `yarn` and `standard-version`.

```bash
# Stage changes
yarn run git:stage

# Commit using Commitizen (cz) for immaculate conventional commits
yarn run git:commit

# Bump versions and generate changelogs automatically
yarn run release:patch  # (or minor / major)
```
Every release drops a tagged changelog and perfectly syncs the `__version__` across the Python module and the node ecosystem.

---

<div align="center">
  <br>
  <i>Stay based, keep compounding those W's. 📈</i><br>
  <b>Copyright (c) 2026 Shan.TK</b>
</div>
