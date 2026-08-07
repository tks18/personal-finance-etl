# FIRE Forecasting Configuration Guide

The FIRE Forecasting engine computes your financial independence progress, sequence of returns risk (SoRR), and runway survival using a compiled Numba stochastic Monte Carlo simulation. Your configuration parameters heavily influence these calculations. 

Because life events drastically alter both the capital required and your earning runway, the configuration should be adapted to mirror your current risk profile. 

This guide breaks down how to fine-tune the `financial_rules.toml` configuration to accommodate an aggressive (optimistic) FIRE approach versus a conservative (highly resilient) approach, and exactly how each parameter affects your dashboard metrics.

---

## The Two Profiles

### 1. The Aggressive (Optimistic) Profile
You assume strong market performance, fewer unplanned expenses, and high career stability. 
- **Goal:** Achieve FIRE numbers faster, assuming your lifestyle won't dramatically shift and your expenses stay near their baseline.
- **Impact on Dashboard:** `Probability_Of_Success_Pct` will model high. `Runway_Months` will stretch further.

### 2. The Conservative (Resilient) Profile
Designed for younger individuals who expect major life events (marriage, kids, healthcare costs) and anticipate economic headwinds. 
- **Goal:** Build an airtight "End Game" portfolio. The model will require significantly more wealth to show a "High Probability of Success."
- **Impact on Dashboard:** `Probability_Of_Success_Pct` is harder to reach 95%+, but when you do, your portfolio is nearly invincible against fat-tailed market crashes.

---

## Key Parameters & Their Impact

### 1. Core Withdrawal & FIRE Rules (`[assumptions.fire]`)
These parameters dictate how fast you accumulate wealth and how much you need to stop working.

| Parameter | Aggressive | Conservative | Impact on Metrics |
| :--- | :--- | :--- | :--- |
| `swr_multiplier` | `25.0` (4%) | `33.3` (3%) | Determines your absolute `Target_FI_Today`. A lower SWR (higher multiplier) drastically increases the capital required, lowering your `Probability_Of_Success_Pct` if you retire early. |
| `lean_fi_ratio` | `0.75` | `0.60` | Multiplier on Target FI for survival mode. Affects `Lean_FI_Today`. Lower ratio = you assume you can survive on less. |
| `coast_fi_real_return` | `0.06` | `0.04` | Assumed compounding rate for Coast FI. A lower return significantly raises the amount of `Coast_FI_Today` you need right now to coast. |
| `cape_swr_floor` | `0.04` | `0.03` | Guyton-Klinger Guardrail. If the market crashes in the simulation, this is the lowest your withdrawal rate can go. A lower floor means you assume you can tighten your belt significantly, which **increases** survival probabilities. |
| `cape_swr_ceiling` | `0.06` | `0.05` | Guyton-Klinger Guardrail. How high your spending can scale in a bull market. A higher ceiling increases lifestyle but slightly degrades long-term safety. |
| `human_capital_max_age`| `65.0` | `50.0` | The age you expect to stop earning. A lower age forces your `Target_FI` to shoulder the load sooner. |

### 2. Capital Market Assumptions (`[assumptions.cma]`)
These define the baseline growth and volatility of your portfolio.

| Parameter | Aggressive | Conservative | Impact on Metrics |
| :--- | :--- | :--- | :--- |
| `expected_real_return` | `0.07` | `0.04` | The average inflation-adjusted return. Directly controls the mean drift of the simulation. A lower return dramatically reduces `Wealth_P50` projections and lowers `Probability_Of_Success`. |
| `fat_tail_multiplier` | `1.0` | `1.3` | Inflates your historical volatility to simulate extreme Black Swan crashes using a Student-T distribution. Higher multiplier drastically increases sequence of returns risk (SoRR), punishing your `Runway_Months_Stressed_P10`. |

### 3. Monte Carlo Simulation Mechanics (`[assumptions.monte_carlo]`)
These parameters dictate the mathematical bounds of the 1,000+ simulation paths.

| Parameter | Aggressive | Conservative | Impact on Metrics |
| :--- | :--- | :--- | :--- |
| `annual_volatility` | `0.12` | `0.18` | Base market volatility. Higher volatility creates wider spreads between your `Wealth_P10` and `Wealth_P90` outcomes. |
| `real_return_floor` | `-0.20` | `-0.40` | Absolute limit on how bad a single year can be in the simulation. A lower floor allows the jump-diffusion model to generate apocalyptic crashes, testing extreme resilience. |
| `desired_target_age` | `85` | `95` | Sets the decumulation lifespan. A longer lifespan (95) requires the portfolio to survive more years, demanding a lower withdrawal rate and reducing `Probability_Of_Success` for early retirees. |

---

## Action Plan for a Resilient Future

If you are currently single and expecting potential marriage, kids, or career changes, it is highly recommended to use the **Conservative** configuration. This prevents the mathematical engine from giving you a false sense of security.

If the dashboard says you have a **90%+ Probability of Success** under the Conservative parameters, you are exceptionally well-positioned to handle whatever life throws at you.

**How to Apply:**
Edit the `financial_rules.toml` inside your repository according to the tables above. 
The ETL pipeline will automatically read the updated `.toml`, parse it through `FinancialRules`, and pipe the exact parameters directly into the Numba Monte Carlo simulation and Polars vectorization engine at runtime.
