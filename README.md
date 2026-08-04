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
    <img alt="Grade" src="https://img.shields.io/badge/Grade-Diamond%20Certified%20%F0%9F%92%8E-000000.svg?style=for-the-badge" />
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

## 💎 The Diamond Standard: Module Breakdown

This pipeline doesn't just log where your fiat went. It actively models risk, tests survival, and mathematically optimizes your capital preservation through a series of strictly decoupled, **SRP-compliant Presentation Builders**.

Here is how each module is engineered to give you unfair levels of financial awareness.

### 🎲 1. Fire Forecasting Engine (`fire_forecasting.py`)
**What it handles:** Long-term wealth projection and Sequence of Returns Risk (SoRR) analysis.
**How it helps:** Stops you from retiring on a naive, straight-line 7% return assumption that gets nuked the second a recession hits.
**The Math (Rizzed up):** We ripped out the standard Geometric Brownian Motion and injected a **Merton Jump-Diffusion Model**. 
*   It runs thousands of Monte Carlo pathways using fat-tailed Student-T distributions.
*   **Poisson Crash Injection:** It autonomously fires Bernoulli trials (`binomial(1, 0.05/12)`) simulating sudden, -20% market collapses. 
*   **The Result:** Your `Probability_Of_Success_Pct` is now hyper-resilient. If the dashboard says you're mathematically free to retire, you can actually sleep at night knowing your model survived simulated black-swan crashes.

### 🏛️ 2. Risk Metrics Engine (`risk_metrics.py`)
**What it handles:** Advanced volatility mapping, drawdown analysis, and Expected Shortfall.
**How it helps:** Eradicates the "Nominal Illusion" by stripping down your portfolio to its bare-metal risk exposure.
**The Math (Rizzed up):** Historical VaR (Value at Risk) is weak because it ignores the magnitude of losses past the 95th percentile. 
*   We replaced basic VaR with **Expected Shortfall (CVaR)** via rolling `.map_elements` Polars aggregations. 
*   It computes exact `NW_Volatility_12M`, `Sharpe_Ratio`, `Sortino_Ratio`, and `Calmar_Ratio` against dynamic risk-free rates. 
*   **The Result:** You see the exact expected loss magnitude of your worst-case scenarios, giving you a definitive floor on your capital preservation.

### 🦅 3. Tax Analytics Engine (`tax_analytics.py`)
**What it handles:** Granular tax liability forecasting and automated Tax-Loss Harvesting (TLH).
**How it helps:** Prevents you from leaking yield to the government and intelligently weaponizes your losses.
**The Math (Rizzed up):** We built a **Tax Alpha Maximizer**. Standard software tells you to just "sell your losers." That's a rookie move that triggers Wash Sale rules and locks you out of the market.
*   Our engine calculates the precise `Net_Tax_Benefit` of every tax-lot based on its `Holding_Type` (STCG/LTCG) and dynamic config rates.
*   **Substitute Asset AI:** It analyzes the `INSTRUMENT_SUBTYPE`. If you are holding a losing Nifty50 ETF, it flags `Substitute_Asset_Available = True` and aggressively bumps its `Priority_Score`.
*   **The Result:** The system explicitly directs you to harvest losses where you can instantly rotate into a correlated proxy asset, generating pure tax-alpha while remaining 100% delta-neutral to the market. 

### 🧠 4. Performance Attribution (`performance_attribution.py`)
**What it handles:** Multi-Level Brinson-Fachler Institutional Performance Attribution.
**How it helps:** Tells you if you are actually a good investor or if you just rode a bull market.
**The Math (Rizzed up):** Naive returns get horribly distorted by mid-month cash flows (e.g., dumping your salary into the market on the 15th). 
*   We engineered a true **Time-Weighted Return** system using the **Modified Dietz** method.
*   Every single transaction generated by the FIFO lot processor is mapped with a `Dietz_Day_Weight` `((Total_Days - Day_Of_Month) / Total_Days)`. 
*   **The Result:** The engine isolates your `Selection_Effect` and `Allocation_Effect` perfectly, giving you a mathematically pure `Total_Active_Return` (Alpha) entirely scrubbed of capital flow noise.

### 🌐 5. Sector Allocation (`sector_allocation.py`)
**What it handles:** Hierarchical exposure mapping and dynamic risk budgeting.
**How it helps:** Stops you from building a high-risk, hyper-correlated glass cannon portfolio.
**The Math (Rizzed up):** We dumped the basic Herfindahl-Hirschman Index (HHI). Just because your money is split 50/50 between Tech stocks and Crypto doesn't mean you're diversified—they are highly correlated.
*   We calculate the exact **Marginal Risk Contribution (MRC)** of every instrument class using rolling covariances mapped natively in Polars: $MRC_i = w_i \frac{Cov(R_i, R_p)}{Var(R_p)}$.
*   **The Result:** The pipeline explicitly highlights which assets are violently driving the volatility of your portfolio, allowing you to rebalance based on actual risk budgets, not just arbitrary target weights.

---

## 🛠️ The Tech Stack (The Ferrari)

- **Core Engine:** `Polars` (Streaming memory DAGs for infinite out-of-core scaling)
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
- **`p_tf_Risk_Metrics`:** Houses the heavy-duty Expected Shortfall, Drawdowns, and Volatility metadata.
- **`p_tf_Performance_Attribution`:** Your Brinson-Fachler alpha scores mapped by sector.
- **`p_tf_Sector_Allocation_Monthly`:** Marginal Risk Contributions and benchmark deviations.
- **`p_tf_Tax_Harvesting`:** The ranked priority list of substitute-friendly assets to harvest.
- **`p_tf_FIRE_Forecast_Stochastic`:** The raw output grid of the Merton Jump-Diffusion pathways.

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
