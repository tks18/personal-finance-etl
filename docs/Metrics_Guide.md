# 📊 Institutional Metrics & Configuration Guide

> [!IMPORTANT]
> Welcome to the Quantitative Master Engine's official metrics guide. Because this engine is built on institutional-grade financial principles, **it strips away simplified "budget tracker" metrics and relies purely on quantitative risk analytics.** 

This guide walks you through every parameter available in the `financial_rules.toml` configuration, exactly how the Quant Engine calculates Alpha, and how to interpret the downstream presentation ratios in your dashboards.

---

## ⚙️ 1. Financial Rules Engine (`financial_rules.toml`)

The engine's logic is dynamically driven by your configuration. Adjusting these parameters fundamentally alters how your data is parsed, how your tax-alpha is harvested, and how your FIRE survival probabilities are mathematically proven.

### Structural Mappings
These arrays map raw categories from your extraction sources to institutional tags, ensuring the engine knows how to treat your cashflow.

*   **`[income.active]` / `[income.dividends]` / `[income.interest]`**: Maps your raw income strings into active vs. passive buckets. If dividends aren't mapped here, the engine won't correctly calculate your *Organic Yield*.
*   **`[expense.core]`**: Maps what you consider "Core" survival expenses (e.g., rent, groceries) vs. discretionary spending. Your FIRE targets are based *exclusively* on core expenses, not discretionary splurges.
*   **`[assets.illiquid]`**: Defines assets like Real Estate or locked EPF. The engine strips these out when calculating *Liquid Liability Coverage* and *Months of Runway*.
*   **`[investments]`**: Identifies which asset subclasses represent your active investment portfolio for Modified Dietz tracking.
*   **`[assumptions.target_allocations]`**: A key-value map defining your target portfolio weights. The engine computes `Benchmark_Deviation` against these weights.

### Macro & Capital Market Assumptions
These act as fallbacks and baseline growth metrics.

*   **`fallback_risk_free_rate`**: The assumed risk-free yield. This directly sets the hurdle rate for your Sharpe and Sortino ratios.
*   **`expected_real_return`**: The expected real (inflation-adjusted) return of your portfolio. Used as the mean drift in the Monte Carlo simulations.
*   **`fat_tail_multiplier`**: Inflates your historical volatility to simulate "fat tails" (extreme drawdowns), recognizing that normal distributions fail to predict black swan crashes.

### Tax-Alpha Engine (`[assumptions.tax]`)
*   **`debt_mf_cutoff_date`**: Hardcoded date where tax rules changed (grandfathering clause for indexation).
*   **`ltcg_thresholds`**: A map defining holding periods before an asset transitions from Short-Term to Long-Term.
*   **`fallback_equity_ltcg_exemption`**: The annual tax-free exemption limit for equity LTCG. 
*   **`harvest_wait_days_threshold`**: The minimum wash-sale period.

---

## 📈 2. Investment Quant Engine Metrics

> [!NOTE]
> This layer evaluates your raw portfolio against the broader market. It completely ignores external cash flows (like your salary) to grade your actual investment acumen.

### True Alpha Generation (Modified Dietz Brinson-Fachler)
*   **The Math**: To completely eradicate cashflow distortion (e.g., depositing a huge chunk of your salary mid-month), the engine assigns an exact **`Dietz_Day_Weight`** to every single transaction. Alpha is then computed on the cashflow-weighted denominator. 
*   **Why it matters**: If your portfolio beat the benchmark, this tells you *why*. Was it because you cleverly overweighted Tech (`Allocation_Effect`), or because you picked the best individual Tech stocks (`Selection_Effect`)?

### Tax-Alpha Harvesting Engine (`p_tf_tax_harvesting`)
The engine scans every single open FIFO lot and flags action items:
*   **`Substitute_Asset_Available`**: The engine actively looks for broad ETFs or Index Funds. If a substitute exists, it mathematically spikes the `Priority_Score`.
*   **The Action**: Sell the asset to capture the `Net_Tax_Benefit` (exact fiat saved in taxes), and immediately buy a perfectly correlated proxy asset to remain market-neutral.
*   **`HARVEST_LTCG_EXEMPT`**: If you have unrealized long-term gains *below* your annual exemption limit, the engine recommends selling and instantly rebuying to lock in a 100% tax-free step-up in cost basis.

### Institutional Risk Metrics (`p_tf_risk_metrics`)
We don't just look at standard deviation. The engine maps extreme downside risk.

*   **Expected Shortfall (CVaR)**: `Expected_Shortfall_95`. Historical VaR tells you the threshold of your worst 5% of months. CVaR takes the mathematical average of those worst 5% of months to tell you exactly how painful a crash will be.
*   **Sharpe & Sortino Ratios**: Measure risk-adjusted return. Sortino specifically ignores upside volatility (making money isn't "risk"). Target **> 1.0**.
*   **Calmar Ratio**: `Rolling_12M_Return / Max_Drawdown_12M`. Evaluates how painful the ride is compared to the destination. Target **> 0.5**.

### Correlation-Adjusted Diversification
*   **Marginal Risk Contribution (`Marginal_Risk_Contribution`)**: The engine replaces the naive HHI index with a covariance matrix approximation. It tells you exactly what percentage of your portfolio's total volatility is driven by a specific sector.

---

## 🏦 3. Core Presentation Metrics (Wealth & Budgeting)

The UI/BI ingestion layer assesses your overall structural financial health.

> [!WARNING]
> Instead of deriving metrics from balancing identities (which creates phantom money), this engine enforces strict ground-truth mapping.

*   **`Liquid_Liability_Coverage_Ratio`**: `Liquid Assets / Total Liabilities`. A strict insolvency stress-test. Demands to know if you can clear your debts *tomorrow* using only liquid capital. Target: **> 1.0**.
*   **`Months_of_Runway`**: `Liquid Assets / Trailing 3M Avg Expenses`. Calculates exactly how many months you can survive a total loss of income. Target: **12.0 to 24.0**.
*   **`Actual_Investment`**: The mathematically pure net flow (`Deployed - Redeemed`) sourced directly from your transaction fact tables. 

---

## 🔥 4. Stochastic FIRE Outputs (`p_tf_fire_forecasting_monthly`)

> [!CAUTION]
> The engine simulates 1,000+ parallel realities traversing 30+ years into the future. **We do not use basic straight-line math.**

### The Merton Jump-Diffusion Engine
The simulation runs on a **Merton Jump-Diffusion** stochastic model utilizing a **Student-T Distribution** (fat tails).
*   **Poisson Crashes**: The engine runs localized Bernoulli trials across the simulation matrix, enforcing a random probability of a sudden 20% market collapse. 
*   **Sequence of Returns Risk (SoRR)**: Because of these simulated crashes, the `Probability_Of_Success_Pct` mathematically tests if your portfolio can survive a devastating black-swan event occurring in the very first year of your retirement. Target: **> 90%**.
*   **Coast FI Engine**: The `@njit` engine gracefully handles Coast FI pathways. If your monthly contributions hit $0, the simulation continues unabated, letting the raw compounding of your existing real wealth mathematically prove your success.

### Stochastic Drifting Targets
*   **Real vs Nominal Sync**: The engine uses your Capital Market Assumptions (`cma_real_return`) to run the core loops entirely in "Real" purchasing power. This perfectly prevents double-counting inflation.
*   **`Target_FI_Future_Nominal_P50`**: The nominal future targets are tracked separately via an Ornstein-Uhlenbeck stochastic inflation process for your dashboard.

**Actionable Insight**: If your `Current_FI_Coverage_Pct` is high against today's target, but your future stochastic nominal projections show a massive gap against `Target_FI_Future`, your portfolio is suffering from cash-drag and will be eroded by stagflation. **Increase `Asset_Velocity_%` to deploy capital!**
