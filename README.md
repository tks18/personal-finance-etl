<div align="center">
  <img src="logo.png" alt="Logo" width="150"/>
  <h1>Shan's Personal Finance ETL 💸✨</h1>
  <p><b>An enterprise-grade, localized Data Warehouse built to track my personal net worth.</b></p>
  <p><i>Because tracking your bags in an Excel sheet in 2026 is pure NPC behavior.</i></p>

  <p>
    <img alt="Python Version" src="https://img.shields.io/badge/Python-3.13+-blue.svg" />
    <img alt="Tech Stack" src="https://img.shields.io/badge/Powered%20by-Polars%20%7C%20ADBC-orange.svg" />
    <img alt="Type Safety" src="https://img.shields.io/badge/Type%20Safety-Strict%20(100%25)-success.svg" />
  </p>
</div>

---

## 🗣️ What is this? (No Cap)

Let's get one thing straight right out of the gate: **this is not a SaaS app or a generic plug-and-play budget tracker**. 

This is my personal, highly customized ETL (Extract, Transform, Load) data warehouse. I built this from scratch to consolidate messy broker logs, scattered mutual fund statements, and raw bank transactions into a single, aggressively optimized `SQLite` database. 

I'm open-sourcing it because gatekeeping architecture patterns is cringe. If you want to see how to build a highly relational, 100% type-safe, multi-processed financial pipeline that calculates quant metrics on your laptop—you've come to the right place. 

*(Disclaimer: My actual portfolio data, net worth, and personal configs are strictly `.gitignore`'d. You won't find my bags here. We stay secure. 🔒)*

---

## 🔥 Key Features (The Flex)

This pipeline doesn't just log expenses. It is a full-fledged quantitative engine designed to yield W's only.

- **Ludicrous Speed (ADBC + Polars):** We skip the slow Python DBAPI completely. By leveraging Rust-backed `Polars` and the `adbc-driver-sqlite`, we map native Arrow memory directly to the database disk. It compiles years of financial history instantly.
- **Enterprise-Grade Tax Engine:** The `PolarsTaxEngine` natively handles complex FIFO lot matching, legacy grandfathering tax laws, and actively splits holdings into STCG/LTCG. Tax loss harvesting is how we stay rich.
- **Market-Calibrated Quant Analytics:** The `BenchmarkEngine` dynamically pulls live market indices from Yahoo Finance (`yfinance`). It maps benchmarks directly to your personal holdings to compute **Alpha, Beta, XIRR, Lot-Level CAGR, and Capture Ratios**.
- **Presentation-Tier BI Engines:** The `WealthPresentationEngine` does the heavy lifting for downstream BI dashboards, auto-aggregating metrics like Months of Runway, Savings Rate, Debt-to-Asset ratios, and Category Inflation Trends.
- **100% Type-Safe Architecture:** Fully typed in Python 3.13. Zero Pylance warnings, zero `Any` types, zero `type: ignore` hacks. 

---

## 🧠 The Data Model (Star Schema)

We do not tolerate spaghetti data in this house. The database is strictly modeled using a dimensional Star Schema, divided into three distinct operational tiers.

### 1. Cash Flow Core (Raw Facts)
Standard Fact (`f_`) tables that track every penny moving through the system:
- **`f_Income_Transactions` & `f_Expense_Transactions`:** Every swipe, salary drop, and purchase categorized down to the molecular level.
- **`f_Transfer_Transactions`:** Safely tracks money moving *between* accounts without artificially double-counting your net worth.
- **`f_Opening_Balances`:** Aggressively deduplicated seeds for starting capital.

### 2. The Investment Zone
Where the Tax and Benchmark engines store their computations:
- **`f_tf_Investment_Purchase_Data` & `f_tf_Investment_Sale_Data`:** Maps every single sell order to its exact buy lot via FIFO.
- **`f_Investment_Market_Data` & `f_Investment_Benchmark_Data`:** Daily tracking of asset valuations vs. delta-fetched Yahoo Finance closing prices.

### 3. The Presentation Tier (`p_tf_`)
Downstream presentation tables specifically designed to be ingested by BI Dashboards. Calculated by the Wealth Engine, ensuring the UI remains clean.
- **`p_tf_Net_Worth_Monthly_Summary`:** Tracks cumulative running balances, `Organic_Yield_%`, `Asset_Velocity_%`, and `Months_of_Runway`.
- **`p_tf_Financial_Ratios_Monthly`:** Tracks structural health like `Savings_Rate_%`, `Debt_to_Asset_Ratio_%`, and `FIRE_Progress_%` based on a 4% SWR.
- **`p_tf_Category_Inflation_Trends`:** Calculates personal hyper-inflation by tracking exactly how your category spending grows MoM and YoY.

### 4. Dimension Mastery (`d_`)
- **`d_Calendar`:** A flawless date table spanning from the year 2000 to the present with Fiscal Years and Weekends.
- **`d_Income_SubCategory`, `d_Expense_Category`, `d_Asset_SubCategory`:** Multi-level hierarchical groupings.
- **`d_tf_Investment_Master` & `d_Investment_Benchmark_Master`:** Golden records for tracked assets.

---

## 🛠️ The Tech Stack 

- **Language:** `Python 3.13+`
- **Engine:** `Polars` (Streaming enabled for infinite out-of-core memory scaling)
- **Database:** `SQLite` + `adbc-driver-sqlite`
- **Frontend UI:** `CustomTkinter` (Dark mode only. Peak aesthetics)
- **Financial Math:** `pyxirr` & `yfinance`
- **Packaging & Package Management:** `uv` & `PyInstaller`

---

## ⚙️ How it Works (Architecture)

If you're a developer looking under the hood, here is how the pipeline runs without blowing up the CPU:

1. **Config-Driven:** The engine dynamically reads a `config.toml` that stores the paths to your raw statement dumps, master dependency CSVs, and target DB folders.
2. **True Multiprocessing:** The `CustomTkinter` UI and the ETL Pipeline live in completely different OS processes. They communicate via `multiprocessing.Queue`. The UI never freezes, even when Polars is chewing through millions of rows.
3. **Decoupled Engines:** Extraction, standard transformation, advanced analytics, and downstream presentation are strictly isolated modules. This Separation of Concerns (SoC) ensures side-effect-free execution.
4. **PyInstaller Bulletproofing:** The entire app, alongside its native C/Rust ADBC extensions, is bundled into a single standalone Windows `.exe` using custom PyInstaller hooks.

---

## 🚀 Developer Quickstart

If you want to fork this and adapt the `csv_extractor.py` and `excel_extractor.py` to your own life, here is the playbook:

### 1. Install Dependencies
We use `uv` for lightning-fast package management. Clone the repo and sync:
```bash
uv sync
```

### 2. Configure your Environment
Create a `config.toml` setting up your source paths (see the codebase for exact key requirements). The GUI automatically remembers your recent configs.

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

We run enterprise-grade SDLC here. Semantic versioning is enforced via `yarn` and `standard-version`.

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
  <i>Stay based, keep stacking those W's. 📈</i><br>
  <b>Copyright (c) 2026 Shan.TK</b>
</div>
