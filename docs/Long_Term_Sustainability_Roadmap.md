# Personal Finance ETL: Long-Term Sustainability & Roadmap

## 1. Executive Summary
The Personal Finance ETL pipeline is currently operating at an institutional-grade level of efficiency. By leveraging Polars for in-memory transformations and DuckDB for analytical storage, the pipeline cleanly processes 1,500+ raw files and completely rebuilds the database in roughly 20 seconds. 

This document outlines the architectural strengths that make this system sustainable, identifies the specific bottlenecks that will arise over the next decade as data volume scales (specifically "The Small Files Problem"), and provides a phased roadmap to ensure the pipeline remains performant, deterministic, and maintainable for decades.

---

## 2. Current Architecture Strengths (The Foundation)
The system is built on highly sustainable patterns that should **not** be changed in the near future:

* **The Polars + DuckDB Stack:** Polars (Rust-based) handles data exponentially faster than traditional libraries like Pandas, while DuckDB provides a zero-infrastructure, portable analytics engine.
* **Idempotent Full Rebuilds:** Dropping and completely recreating the `.duckdb` file on every run is a massive advantage. It entirely eliminates "incremental state corruption" (e.g., an old deleted transaction lingering in the database). DuckDB can write a 2GB database in seconds, meaning this full-rebuild strategy will remain viable indefinitely.
* **Configuration-Driven Rules:** Decoupling hardcoded assumptions (tax brackets, inflation rates, target allocations) into `financial_rules.toml` ensures the system can adapt to life changes without requiring Python code rewrites.

---

## 3. The 10-Year Bottleneck: "The Small Files Problem"
While the data size itself is trivial (1,500 Excel files at ~50kb = ~75MB), the **quantity** of files is the only looming threat to performance.

* **The Math:** Assuming a similar rate of transaction exports, in 10 years, the raw directory will contain 15,000 to 20,000 individual Excel/CSV files totaling roughly 1GB.
* **The Bottleneck:** Polars can process 1GB of data in milliseconds. The bottleneck will be **OS File I/O**. Requesting the operating system to open, read headers, scan, and close 20,000 separate files across a hard drive will introduce massive I/O overhead, eventually ballooning the 20-second runtime into several minutes.

---

## 4. Roadmap & Incremental Upgrades

### Phase 1: Near-Term Hardening (Months 1–12)
Focus on stability, data contracts, and preventing "code rot."
* **Quantitative Unit Testing:** As the `src/engines/` layer becomes more complex (Expected Shortfall, Tax-Loss Harvesting, Jump-Diffusion), manual validation becomes impossible. Introduce a lightweight `pytest` suite that runs mock portfolio data through the engines to mathematically prove the output remains correct after any code changes.
* **Schema Validation (Data Contracts):** Brokers and banks frequently change their CSV export formats (e.g., renaming "Symbol" to "Ticker"). Implement a data validation layer (like `pandera` or explicit Polars schema assertions) at the *ingestion boundary*. If a source format changes, the pipeline should fail loudly at step 1 with a clear error, rather than crashing deep inside a complex transformation join.
* **Read/Write Decoupling:** OneDrive synchronization can lock the `.duckdb` file if Power BI is reading it while the Python ETL is writing it. Ensure the ETL writes to a staging file (e.g., `pf_prod_staging.duckdb`) and executes an atomic copy to the final read file only upon completion, preventing BI dashboard crashes.

### Phase 2: Solving the I/O Bottleneck & Rule Decay (Years 2–4)
As pipeline execution creeps toward the 45–60 second mark, optimize ingestion and rule management.
* **Parquet Staging (Bronze Layer):** Stop having the main pipeline read thousands of raw Excel files. Implement a pre-processing ingestion script that runs on a schedule. It identifies *only new* Excel files and appends them to a single, compressed `historical_transactions.parquet` file. Reading a 1GB Parquet file takes Polars ~0.2 seconds, instantly dropping the total pipeline runtime back down to 10-15 seconds.
* **Categorization Rule Migration:** Currently, categorization mappings (`active_cat`, `core_cat`) are managed in `financial_rules.toml`. Over a decade, as new merchants and life events occur, this TOML file will become unwieldy. Migrate these classification arrays into a dedicated master mapping table (CSV/Excel) that is joined dynamically, making maintenance easier.

### Phase 3: Total Automation & State Roll-Ups (Years 5–10)
Focus on removing human friction and managing decades of historical computation.
* **Cross-Year State Management (Taxes & Performance):** Replaying 10 years of granular tax events (e.g., compounding Long-Term Capital Loss carryforwards) on every run will eventually slow down the analytics engines. Introduce a "roll-up" mechanism: mathematically lock historical years (e.g., saving the closing tax state of 2025) and only compute the current year dynamically.
* **Automated API Ingestion:** Manually exporting CSVs from brokers is the weakest link for long-term consistency. Build automated API connectors (via Plaid, Yodlee, or direct broker APIs) to pull raw data directly into the Bronze Parquet layer on a daily cron job.
* **Incremental Benchmark Feeds:** Querying 20+ years of daily market tick data for thousands of global tickers during Monte Carlo simulations will become heavy. Transition the `stg_mkt` benchmark feeds to an incremental upsert model in a persistent DuckDB sidecar database.
