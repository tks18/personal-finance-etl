<div align="center">
  <img src="logo.png" alt="Logo" width="180"/>
  <h1>Shan's Personal Finance Quant Engine 💸✨</h1>
  <p><b>An institutional-grade, hyper-optimized Quantitative Master Engine built to absolutely dominate personal net worth.</b></p>
  <p><i>Because tracking your portfolio in a basic spreadsheet or a SaaS pie-chart app is officially outdated.</i></p>

<p>
    <img alt="Python Version" src="https://img.shields.io/badge/Python-3.13+-blue.svg?style=for-the-badge&logo=python&logoColor=white" />
    <img alt="Tech Stack" src="https://img.shields.io/badge/Engine-Polars%20%7C%20DuckDB-FF8C00.svg?style=for-the-badge" />
    <img alt="Architecture" src="https://img.shields.io/badge/Architecture-Event%20Driven%20DAG-8A2BE2.svg?style=for-the-badge" />
  </p>
</div>

---

## 🗣️ The Manifesto

Let's get one thing straight right out of the gate: **this is not a generic, plug-and-play budget tracker.**

Retail personal finance apps focus on one thing: **budgeting**. They show you a colorful pie chart of your coffee expenses and pat you on the back. But true wealth is not created by aggressively auditing your Starbucks habit; wealth is created through asymmetric risk management, capital velocity, and tax alpha.

This engine is a **Sovereign Wealth Management Pipeline**. It treats your household balance sheet like a multi-million dollar quantitative fund. I built this monolith from scratch to ingest messy broker logs, scattered mutual fund statements, and raw bank transactions, and forge them into a single, aggressively performant `DuckDB` data warehouse driven by a `Polars` execution DAG.

I'm open-sourcing the engine because gatekeeping institutional architecture patterns is unnecessary. If you want to see how to build a highly relational, 100% type-safe financial pipeline that calculates true Modified Dietz cashflows, actively hunts tax-alpha, and runs stochastic Monte Carlo survival simulations on your laptop—you have arrived.

*(Disclaimer: My actual portfolio data, net worth, and personal TOML configs are strictly `.gitignore`'d. We stay secure. 🔒)*

---

## 💎 How This Solves Personal Finance Management

This architecture replaces "guessing" with deterministic mathematics. It actively models risk, tests survival, and mathematically optimizes your capital preservation through a series of strictly decoupled, **SRP-compliant Presentation Builders**.

Here is how each module is engineered to give you an unfair level of financial awareness.

### 🎲 1. Decumulation & FIRE Forecasting (`fire_mc_sim.py`)

**The Problem:** Most FI calculators use a naive, straight-line 7% return assumption, completely ignoring Sequence of Returns Risk (SoRR) and double-counting inflation. If a recession hits the year you retire, your spreadsheet model shatters.
**The Edge:** We ripped out standard Geometric Brownian Motion and injected a **Merton Jump-Diffusion Model**.

* **Real-Return Perfection:** Computes all matrix pathways natively in Real Returns. Nominal targets are dynamically drifted via Ornstein-Uhlenbeck stochastic inflation logic—absolutely no double-counted inflation bugs here.
* **Fat-Tailed Risk:** Evaluates risk via Student-T distributions (df=4) and executes Poisson Bernoulli trials (`binomial(1, 0.05/12)`) simulating sudden, -20% Black Swan market collapses.
* **Institutional Decumulation:** Implements **Guyton-Klinger dynamic withdrawal rules** directly into the `@njit` Numba loops. If the market crashes in retirement, the engine algorithmically models you taking a 10% lifestyle cut to survive.
* **Coast FI Engine:** Seamlessly handles individuals who halt savings (`pmt = 0`), testing if raw compounding alone can carry the portfolio over the finish line.

### 🏛️ 2. Institutional Risk Engine (`risk_metrics.py`)

**The Problem:** "Risk" in retail apps is just a color (Red/Green). You don't know the actual dollar amount of exposure your portfolio faces when volatility spikes.
**The Edge:** Historical VaR (Value at Risk) is weak because it ignores the magnitude of losses past the 95th percentile.

* We replaced basic VaR with **Expected Shortfall (CVaR)** via rolling `.map_elements` Polars aggregations.
* It computes exact `NW_Volatility_12M`, `Sharpe_Ratio`, `Sortino_Ratio`, and `Calmar_Ratio` against dynamic risk-free rates.
* **The Result:** You see the exact expected loss magnitude of your worst-case scenarios, giving you a definitive floor on your capital preservation.

### 🦅 3. Tax Alpha Maximizer (`tax_analytics.py`)

**The Problem:** You leak basis points of yield to taxes every year because you don't intelligently offset your gains. Standard software just tells you to "sell your losers," which is a rookie move that triggers Wash Sale rules.
**The Edge:** We built an automated Tax-Loss Harvesting AI.

* Our engine calculates the precise `Net_Tax_Benefit` of every tax-lot based on its `Holding_Type` (STCG/LTCG) and dynamic config rates.
* **Substitute Asset AI:** It analyzes the `INSTRUMENT_SUBTYPE`. If you are holding a losing Nifty50 ETF, it flags `Substitute_Asset_Available = True` and aggressively bumps its `Priority_Score`.

### 🧠 4. Time-Weighted Performance Attribution (`performance_attribution.py`)

**The Problem:** Naive returns get horribly distorted by mid-month cash flows (e.g., dumping your salary into the market on the 15th). It's impossible to tell if you're a skilled investor or just riding a bull market.
**The Edge:** Multi-Level **Brinson-Fachler Institutional Attribution**.

* We engineered a true Time-Weighted Return system using the **Modified Dietz** method. Every single transaction generated by the FIFO lot processor is mapped with a `Dietz_Day_Weight`.
* **The Result:** The engine isolates your `Selection_Effect` and `Allocation_Effect` perfectly, giving you a mathematically pure `Total_Active_Return` (Alpha) entirely scrubbed of capital flow noise.

### 🌐 5. Platinum-Grade Ground Truth Budgeting (`budget_forecast.py`)

**The Problem:** Budget apps "guess" your investments by deriving balancing figures (Income - Expense), creating phantom cash flows that destroy data integrity. They also rely on naive row-based rolling averages.
**The Edge:** A fully time-aware execution graph that leverages exact transactional deployments.

* **Time-Aware Polars Windows**: Uses strict `rolling_mean_by("MONTH_START_DATE")` temporal functions. Missing ledger months will never skew your multi-month averages again.
* **Exact Deployment Mapping**: `Investment_Deployed` and `Investment_Redeemed` are joined *directly* from the `df_f_tf_inv_purchase` tables. Your `Actual_Savings` metric is 100% ground-truth.

---

## 🛠️ The Tech Stack

- **Core Engine:** `Polars` (Streaming memory DAGs for infinite out-of-core scaling, taking full advantage of Projection and Predicate pushdowns)
- **Data Warehouse:** `DuckDB` (Columnar, lightning-fast disk synchronization with strict DDL schema validation via `Pandera`)
- **Source Extractor:** `SQLite` + `adbc-driver-sqlite` (Zero-copy Arrow memory transfers)
- **Financial Math:** `pyxirr`, `numpy`, `scipy`, and `Numba` (`@njit`) for hyper-compiled stochastic math
- **Control Panel:** `CustomTkinter` (Dark mode only. Peak aesthetics)

---

## ⚙️ The Pipeline Architecture

If you're a developer looking under the hood, here is how the monolith is engineered to never crash:

1. **Phase 1 (Gatekeeper Extraction):** Raw CSVs, Excel binaries, and SQLite databases are pulled into memory. The system runs an instant `head(1)` fail-fast Polars evaluation to guarantee schema integrity before wasting a single CPU cycle.
2. **Phase 2 (The Transformation DAG):** A strictly decoupled Directed Acyclic Graph harmonizes currencies, maps hierarchical dimensions, and dedupes all historical state using `LazyFrame` structures.
3. **Phase 3 (Quant Analytics):** The `WealthPresentationEngine` takes over. Time-aware rolling functions and Numba JIT-compiled Monte Carlo batches execute parallel computations across your CPU cores.
4. **Phase 4 (DuckDB Materialization):** The presentation layer (`p_tf_` tables) is aggressively materialized and flushed directly to the local `DuckDB` columnar file.

---

## 🗄️ The Data Warehouse (Star Schema)

The downstream database is rigorously modeled and entirely BI-ready. No complex DAX required.

### 📊 The Presentation Tier (`p_tf_`)

- **`p_tf_Net_Worth_Monthly_Summary`:** Tracks cumulative running balances, Organic Yields, Asset Velocity, and `Months_of_Runway`.
- **`p_tf_Budget_Forecast_Monthly`:** Time-aware ground-truth budgeting, incorporating Z-Score anomaly detection and exact `Investment_Deployed` metrics.
- **`p_tf_Risk_Metrics`:** Houses the heavy-duty Expected Shortfall, Drawdowns, and Volatility metadata.
- **`p_tf_Performance_Attribution`:** Your Brinson-Fachler alpha scores mapped by sector.
- **`p_tf_Tax_Harvesting`:** The ranked priority list of substitute-friendly assets to harvest.
- **`p_tf_FIRE_Forecast_Stochastic`:** The raw output grid of the Merton Jump-Diffusion pathways.

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

<div align="center">
  <br>
  <i>Keep compounding, stay ahead of the curve. 📈</i><br>
  <b>Copyright (c) 2026 Shan.TK</b>
</div>
