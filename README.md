<div align="center">
  <img src="logo.png" alt="Logo" width="180"/>
  <h1>Shan's Personal Finance Quant Engine 💸✨</h1>
  <p><b>The undisputed GOAT of personal wealth management frameworks. Built to literally mog your net worth into the stratosphere.</b></p>
  <p><i>Because tracking your portfolio in a basic spreadsheet or SaaS pie-chart app is officially NPC energy. We play on hard mode.</i></p>

<p>
    <img alt="Python Version" src="https://img.shields.io/badge/Python-3.13+-blue.svg?style=for-the-badge&logo=python&logoColor=white" />
    <img alt="Tech Stack" src="https://img.shields.io/badge/Engine-Polars%20%7C%20DuckDB-FF8C00.svg?style=for-the-badge" />
    <img alt="Architecture" src="https://img.shields.io/badge/Architecture-Event%20Driven%20DAG-8A2BE2.svg?style=for-the-badge" />
  </p>
</div>

---

## 🗣️ The Manifesto

Let's keep it a buck fifty: **this is not your average, plug-and-play budgeting tracker.**

Retail personal finance apps focus on one thing: **budgeting**. They show you a colorful pie chart of your Doordash expenses, pat you on the back, and call it a day. That is a massive L. True wealth is not created by aggressively auditing your $6 iced coffee habit; wealth is created through asymmetric risk management, compounding capital velocity, and weaponized tax alpha.

This engine is a **Sovereign Wealth Management Pipeline**. It treats your household balance sheet like a multi-million dollar quantitative hedge fund. I built this monolith from scratch to ingest messy broker logs, scattered mutual fund statements, and raw bank transactions, and forge them into a single, aggressively performant `DuckDB` data warehouse driven by a `Polars` execution DAG. It is strictly Medallion-architecture compliant and hyper-optimized.

I'm open-sourcing the engine because gatekeeping institutional architecture patterns is mid. If you want to see how to build a highly relational, 100% type-safe financial pipeline that calculates true Modified Dietz cashflows, actively hunts tax-alpha, and runs stochastic Monte Carlo survival simulations on your laptop—you have arrived. Welcome to absolute peak performance.

*(Disclaimer: My actual portfolio data, net worth, and personal TOML configs are strictly `.gitignore`'d. We stay secure. 🔒)*

---

## 🔮 The Realities of Forecasting (A Vibe Check)

**Reality Check:** No cap, this is a forecasting model. Real life is going to throw plot twists at you—markets crash, inflation spikes, you might get laid off, or you might hit a massive windfall. A simulation cannot predict the exact day you hit your FI (Financial Independence) number. 

**But here's the alpha:** While the map is not the territory, having a mathematically rigorous framework gives you a ridiculously high-conviction target for your future. This engine doesn't just guess; it stress-tests your life against 10,000 apocalyptic futures to ensure that when life happens, your portfolio doesn't get zeroed out. It gives you the ultimate peace of mind to touch grass and vibe, knowing the math has your back.

---

## 💎 How This Engine Flexes on Traditional Finance

This architecture replaces "guessing" with deterministic mathematics. It actively models risk, tests survival, and mathematically optimizes your capital preservation through a series of strictly decoupled, **SRP-compliant Presentation Builders**.

Here is how each module is engineered to give you an unfair, GOAT-tier level of financial awareness.

### 🎲 1. The Stochastic FIRE Engine (`fire_mc_sim.py`)
**The Vibe:** Most FI calculators use a naive, straight-line 7% return assumption. That's delusional. If a recession hits the year you retire, your spreadsheet model shatters completely.
**The Edge:** We ripped out standard geometric logic and injected a fully Numba-compiled, **State-Aware Monte Carlo Engine** that runs thousands of parallel futures natively in Real Returns.

* **Macro Regime Engine (Markov Chains):** Markets aren't static. We use a **3x3 Markov Transition Matrix** to simulate prolonged Bull, Bear, and Stagflation regimes. If the simulation falls into Stagflation, your inflation targets spike and drift goes flat.
* **Correlated Human Capital Shocks:** Bad things happen together. If the simulation enters a Bear or Stagflation state, it rolls the dice on an **Income Shock** (job loss/zero bonus) that zeroes out your savings rate (`pmt = 0`) for up to 12 months. Pure survival mode testing.
* **Algorithmic Glide Path (Bond Tent):** Protects against Sequence of Returns Risk (SORR) by mechanically de-risking your portfolio into stable assets right before your FI date, and slowly re-risking post-FI to ensure you survive a 40-year retirement.
* **Institutional Decumulation (Guyton-Klinger):** Implements dynamic withdrawal guardrails directly into the `@njit` loops. If the market crashes in retirement, the engine algorithmically models you taking a lifestyle cut (lowering SWR) to survive.
* **Stochastic Inflation & Jump Diffusion:** Uses an Ornstein-Uhlenbeck process to model hyper-realistic, mean-reverting inflation paths, and Merton Jump-Diffusion mechanics to inject instantaneous Black Swan market crashes independent of standard volatility.
* **Coast FI Engine:** Seamlessly handles individuals who halt savings to test if raw compounding alone can carry the portfolio over the finish line.

### 🏛️ 2. Institutional Risk Engine (`risk_metrics.py`)
**The Vibe:** "Risk" in retail apps is just a color (Red/Green) or a vague warning. You don't know the actual dollar amount of exposure your portfolio faces when volatility spikes.
**The Edge:** Historical VaR (Value at Risk) is weak because it ignores the magnitude of losses past the 95th percentile. We replaced it with **Expected Shortfall (CVaR)** via rolling `.map_elements` Polars aggregations.

* Computes exact `NW_Volatility_12M`, `Sharpe_Ratio`, `Sortino_Ratio`, and `Calmar_Ratio` against dynamic risk-free rates.
* **The Result:** You see the exact expected loss magnitude of your worst-case scenarios, giving you a definitive floor on your capital preservation. No more guessing your downside.

### 🦅 3. Tax Alpha Maximizer (`tax_analytics.py`)
**The Vibe:** You leak basis points of yield to taxes every year because you don't intelligently offset your gains. Standard software just tells you to "sell your losers," which is a rookie move that triggers Wash Sale rules.
**The Edge:** We built an automated Tax-Loss Harvesting AI.

* Our engine calculates the precise `Net_Tax_Benefit` of every tax-lot based on its `Holding_Type` (STCG/LTCG) and dynamic config rates.
* **Substitute Asset AI:** It analyzes the `INSTRUMENT_SUBTYPE`. If you are holding a losing Nifty50 ETF, it flags `Substitute_Asset_Available = True` and aggressively bumps its `Priority_Score` so you can harvest the loss and stay exposed to the market. Unfathomably based.

### 🧠 4. Time-Weighted Performance Attribution (`performance_attribution.py`)
**The Vibe:** Naive returns get horribly distorted by mid-month cash flows (e.g., dumping your salary into the market on the 15th). It's impossible to tell if you're a skilled investor or just riding a bull market.
**The Edge:** Multi-Level **Brinson-Fachler Institutional Attribution**.

* We engineered a true Time-Weighted Return system using the **Modified Dietz** method. Every single transaction generated by the FIFO lot processor is mapped with a `Dietz_Day_Weight`.
* **The Result:** The engine isolates your `Selection_Effect` and `Allocation_Effect` perfectly, giving you a mathematically pure `Total_Active_Return` (Alpha) entirely scrubbed of capital flow noise.

### 🌐 5. Platinum-Grade Ground Truth Budgeting (`budget_forecast.py`)
**The Vibe:** Budget apps "guess" your investments by deriving balancing figures (Income - Expense), creating phantom cash flows that destroy data integrity. They also rely on naive row-based rolling averages that break if you miss a month.
**The Edge:** A fully time-aware execution graph that leverages exact transactional deployments and institutional logic.

* **Time-Aware Polars Windows**: Uses strict `rolling_mean_by("MONTH_START_DATE")` temporal functions. Missing ledger months will never skew your multi-month averages again.
* **Z-Score Anomaly Detection:** Your spending is run through a 6-month rolling baseline to calculate `Core_Expense_ZScore` and `NonCore_Expense_ZScore`. If you overspend by 2 standard deviations, the engine flags `Is_Expense_Anomaly`.
* **Exact Deployment Mapping**: `Investment_Deployed` and `Investment_Redeemed` are joined *directly* from the core transactional logs. Your `Actual_Savings` metric is 100% ground-truth.

---

## 🛠️ The Tech Stack (Under the Hood)

- **Core Engine:** `Polars` (Streaming memory DAGs for infinite out-of-core scaling, taking full advantage of Projection and Predicate pushdowns)
- **Data Warehouse:** `DuckDB` (Columnar, lightning-fast disk synchronization with strict DDL schema validation via `Pandera`)
- **Source Extractor:** `SQLite` + `adbc-driver-sqlite` (Zero-copy Arrow memory transfers)
- **Financial Math:** `pyxirr`, `numpy`, `scipy`, and `Numba` (`@njit`) for hyper-compiled stochastic math matrices.
- **Control Panel:** `CustomTkinter` (Dark mode only. Peak aesthetics)

---

## ⚙️ The Pipeline Architecture (Medallion Pattern)

If you're a developer looking under the hood, here is how the monolith is engineered to never crash:

1. **Phase 1 (Gatekeeper Extraction - Bronze):** Raw CSVs, Excel binaries, and SQLite databases are pulled into memory. The system runs an instant `head(1)` fail-fast Polars evaluation to guarantee schema integrity before wasting a single CPU cycle.
2. **Phase 2 (The Transformation DAG - Silver):** A strictly decoupled Directed Acyclic Graph harmonizes currencies, maps hierarchical dimensions, and dedupes all historical state using `LazyFrame` structures.
3. **Phase 3 (Quant Analytics - Gold):** The `WealthPresentationEngine` takes over. Time-aware rolling functions and Numba JIT-compiled Monte Carlo batches execute parallel computations across your CPU cores.
4. **Phase 4 (DuckDB Materialization):** The presentation layer (`p_tf_` tables) is aggressively materialized and flushed directly to the local `DuckDB` columnar file.

---

## 🗄️ The Data Warehouse (Star Schema)

The downstream database is rigorously modeled and entirely BI-ready. No complex DAX required—just plug it into PowerBI, Superset, or Metabase and let it rip.

### 📊 The Presentation Tier (`p_tf_`)

- **`p_tf_Net_Worth_Monthly_Summary`:** Tracks cumulative running balances, Organic Yields, Asset Velocity, and `Months_of_Runway`.
- **`p_tf_Budget_Forecast_Monthly`:** Time-aware ground-truth budgeting, incorporating Z-Score anomaly detection, Rule Targets (40/20/30), and exact `Actual_Investment` metrics.
- **`p_tf_Wealth_Risk_Analytics`:** Houses the heavy-duty Expected Shortfall, Drawdowns, Volatility metadata, and all advanced Monte Carlo output vectors (`Terminal_Wealth_P50`, `Peak_Inflation_Experienced_Pct`, etc.).
- **`p_tf_Performance_Attribution`:** Your Brinson-Fachler alpha scores mapped by sector.
- **`p_tf_Investment_Analytics`:** The ranked priority list of substitute-friendly assets to harvest for tax alpha.
- **`p_tf_Monthly_Cashflow_Summary`:** Exact bifurcation of active vs passive income and precise tracking of equity/debt deployments.

---

## 🚀 Developer Quickstart

If you want to fork this and adapt the codebase to your own life, here is the playbook:

### 1. Install Dependencies
We use `uv` for lightning-fast package management. Clone the repo and sync:
```bash
uv sync
```

### 2. Configure your Environment
Create your `config.toml` (data paths) and `financial_rules.toml` (tax rates, macro fallback assumptions, advanced stochastic modeling parameters, target allocations). The GUI automatically remembers your recent environments.

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
