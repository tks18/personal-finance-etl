<div align="center">
  <img src="logo.png" alt="Logo" width="150"/>
  <h1>Shan's Personal Finance ETL 💸✨</h1>
  <p><b>Open-sourcing the secret sauce to my entire financial existence.</b></p>
  <p><i>Because tracking your bags shouldn't give you L's.</i></p>
</div>

---

## 🗣️ Wait, What is this? (No Cap)

Okay, let's get one thing straight right out of the gate: **this is not a SaaS app or a generic plug-and-play product**. This is literally my personal, highly-customized ETL (Extract, Transform, Load) data warehouse that I built from scratch to flex on my own net worth.

I'm open-sourcing it because gatekeeping is cringe, and maybe you can learn some enterprise-grade architecture patterns from my unhinged obsession with data engineering. If you're still manually tracking your cash flows and stock gains in messy Excel sheets... highkey, you're living like an NPC. I built this absolute unit of a pipeline to take my raw, chaotic broker and bank statements and blast them into a highly relational `SQLite` database.

*(Disclaimer: My actual portfolio data, net worth, passwords, and personal configs are strictly `.gitignore`'d. You won't find my bags here. We stay secure. 🔒)*

---

## 🔥 Why it's goated (The Flex)

- **Unified Wealth Data Warehouse:** It takes messy broker logs, mutual fund statements, and raw bank transactions and flawlessly merges them into a pristine Star Schema. No more manually stitching Excel files together like a boomer.
- **Enterprise-Grade Quant Engine:** The `PolarsTaxEngine` doesn't just do basic math. It handles complex FIFO lot matching, archaic grandfathering tax laws, and calculates XIRR, Lot-Level CAGR, Tracking Error, and Beta. It's basically a hedge fund analyst running locally on your laptop.
- **Ludicrous Speed (ADBC + Polars):** We skip the slow Python DBAPI completely. By using `Polars` and the `adbc-driver-sqlite`, we yeet native Arrow memory directly to the database disk. It compiles your entire financial history faster than you can blink.
- **Market-Calibrated Analytics:** The `BenchmarkEngine` dynamically pulls live market indices from Yahoo Finance (`yfinance`) and maps them directly to your personal holdings. We use this to compute Alpha, Beta, and Capture Ratios so you actually know if you're beating the market or just getting lucky. Pure W rizz.
- **Aesthetic 1-Click Execution:** A clean, custom dark-mode GUI. Select your config, hit run, and watch the progress bar go brrr. No bloat, no confusing menus.

---

## ⚙️ The `config.toml` (The Keys to the Kingdom)

Because we don't hardcode paths like amateurs, the entire pipeline is driven by a `config.toml` file. It's the blueprint that tells the engine exactly where to hunt for data. Here is the vibe:

```toml
# Where the old MoneyManager SQLite DBs live
SOURCE_DB_FOLDER = "...\\SOURCE_DB.db"

# Where the ultra-fast Polars engine drops the new SQLite data warehouse
TARGET_DB_BASE_PATH = "...\\outputs"

# The Static Master Dependencies (The Lore)
COLUMN_MASTER_PATH = "...\\COLUMN_MASTER.csv"
MF_ISIN_CSV_PATH = "...\\MF_ISIN_MAPPING.csv"
BENCHMARK_MAPPING_CSV_PATH = "...\\BENCHMARK_MAPPING.csv"
BENCHMARK_MASTER_CSV_PATH = "...\\BENCHMARK_MASTER.csv"
TAX_RATES_CSV_PATH = "...\\TAX_RATES.csv"
OPENING_BALANCE_CSV_PATH = "...\\OPENING_BALANCE.csv"

# The messy broker dump folder
STATEMENTS_FOLDER = "...\\Statements"
```

*Pro Tip: You can have multiple `.toml` files (e.g. `test_config.toml` vs `prod_config.toml`) and the UI will literally remember your top 10 most used configs automatically.*

---

## 📈 Investment Analytics (The Tax Engine Deep Dive)

The `PolarsTaxEngine` is the absolute final boss of this repository. It doesn't just calculate your total returns and call it a day. It is a full-fledged quantitative engine doing the most:

- **FIFO Lot Matching:** When I sell a stock, the engine iterates back in time in memory and matches the sell order to the *exact* buy lot (First-In, First-Out). It doesn't guess my profits; it knows them down to the exact decimal.
- **Tax Harvesting (Realized vs Unrealized):** It dynamically splits my portfolio into Short-Term Capital Gains (STCG) and Long-Term Capital Gains (LTCG). It even reads the `Tax_Rates.csv` to know the exact `Age_Days` threshold for the financial year.
- **Grandfathering Logic:** It understands legacy tax laws and protects my pre-2018 grandfathered equity gains from double-taxation.
- **Quant Metrics:** We're computing **Lot-Level CAGR**, **XIRR** across the entire holding period, **Beta** (to see how volatile my bags are), **Active Returns** (Alpha), and **Upside/Downside Capture ratios**. If you aren't benchmarking your trades against the market, you're flying blind.

---

## 🧠 The Data Model (The Star Schema Lore)

Since this is my personal vault, here is exactly how I model my financial life under the hood. I built a strict, enterprise-grade **Star Schema** design because we do not tolerate spaghetti data in this house.

### 💸 1. Cash Flow Engineering (The Fact Tables)

We track every single penny that enters or leaves my life. The ETL builds these massive Fact tables:

- **`f_Income_Transactions` & `f_Expense_Transactions`:** Every swipe, salary drop, and impulsive purchase is categorized down to the molecular level.
- **`f_Transfer_Transactions`:** Tracks money moving *between* my own accounts so I don't accidentally double-count my net worth like a rookie.
- **`f_Opening_Balances`:** Seeds the starting capital so cash-flow algorithms don't break spacetime.

### 📥 2. The Final Staging Zone

- **`f_tf_Investment_Purchase_Data` & `f_tf_Investment_Sale_Data`:** Maps every single sell order to its exact buy lot.
- **`stg_Investment_Market_Data` & `f_Investment_Market_Data`:** Daily valuations for every asset I own.
- **`f_Investment_Benchmark_Data`:** Delta-fetches daily closing prices of benchmarks from Yahoo Finance.

### 🗃️ 3. Dimension Mastery (The 'D' Tables)

To make my BI dashboards look immaculate, the ETL generates these highly structured dimensions:

- **`d_Calendar`:** A flawless date table with Fiscal Years, Quarters, and Weekend flags.
- **`d_Income_Category`, `d_Expense_Category`, `d_Asset_Category`:** Multi-level hierarchical categories.
- **`d_Currency` & `d_Tax_Rates`:** Forex and temporal tax bands.
- **`d_tf_Investment_Master` & `d_Investment_Benchmark_Master`:** Golden records of every asset and index tracked in my ecosystem.

---

## 🛠️ Tech Stack (The Built-Different Blueprint)

- **Core Engine:** Python 3.13+ (because we live in the future).
- **Data Manipulation:** `Polars` (Built in Rust 🦀, absolutely mogs the competition).
- **Database Backend:** `SQLite` + `adbc-driver-sqlite` (Zero-copy Arrow memory maps for instant writes).
- **Frontend / UI:** `CustomTkinter` (Dark mode only, obviously).
- **Financial Math / Quants:** `pyxirr` & `yfinance`.
- **Packaging:** `PyInstaller` (Compiled into a single, standalone Windows `.exe` with custom branding).

---

## 🚀 How to go about it (The Playbook)

Since this is heavily tailored to my specific broker formats, it won't just magically work on yours out of the box. But if you want to fork it and adapt the `excel_parser.py` logic to your own life, let him cook:

### 1. Install the vibes

We use `uv` for lightning-fast package management. Install it, clone the repo, and run:

```bash
uv sync
```

### 2. Configure

Create a `config.toml` setting up your source paths (use the blueprint above). The UI automatically remembers your recent configs so you don't have to keep digging for them.

### 3. Run or Build

We got custom CLI entry points up in here.

```bash
# Run in dev mode with hot-reloading (via tkreload)
uv run dev

# Build a standalone EXE using PyInstaller
uv run build
```

This drops a sleek `Shan's Personal Finance ETL.exe` straight into your dist folder, fully bundled with native C/Rust ADBC extensions.

---

## 🏗️ The Pipeline Architecture (Under the Hood)
If you're a gigabrain developer looking at the code, here is how the actual pipeline runs without blowing up your PC:
- **True Multiprocessing:** The UI and the ETL Pipeline live in completely different OS processes. We use `multiprocessing.Queue` to pipe log messages from the heavy data engine straight into the `CustomTkinter` UI. The UI literally never freezes, even when processing millions of rows.
- **PyInstaller Bulletproofing:** Ever tried compiling a massive data app into a `.exe`? It’s a nightmare. I injected PyInstaller hooks to specifically compile native C/Rust binaries (`adbc_driver_sqlite`) so the executable stays totally standalone. No dependencies required on the host machine.
- **Professional `src/` Layout:** This isn't a messy script dump. We use a strictly decoupled `src/` layout. Extraction, transformation, loading, and the UI are all isolated domains.

---

## 💅 The Glow-Up Cycle (Semantic Releases)
We don't just push to main and pray. This repo has a meticulously crafted release cycle powered by `yarn` and `standard-version`. 
Because why track your personal finance if you can't even track your own software versions?

```bash
# Stage changes
yarn run git:stage

# Commit using Commitizen (cz) for immaculate conventional commits
yarn run git:commit

# Push to dev branch
yarn run git:push

# Bump versions and generate changelogs automatically
yarn run release:patch  # (or release:minor / release:major)
```
Every release drops a tagged changelog, updating `__version__ = "0.1.0"` across the python package (`src/__init__.py`) and `package.json` files. We run enterprise-grade SDLC in this house.

---

<div align="center">
  <br>
  <i>Stay based, keep stacking those W's. 📈</i><br>
  <b>Copyright (c) 2026 Shan.TK</b>
</div>
