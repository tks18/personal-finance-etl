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

| Parameter                 | Aggressive    | Conservative  | Impact on Metrics                                                                                                                                                                                                                           |
| :------------------------ | :------------ | :------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `swr_multiplier`        | `25.0` (4%) | `33.3` (3%) | Determines your absolute `Target_FI_Today`. A lower SWR (higher multiplier) drastically increases the capital required, lowering your `Probability_Of_Success_Pct` if you retire early.                                                 |
| `lean_fi_ratio`         | `0.75`      | `0.60`      | Multiplier on Target FI for survival mode. Affects `Lean_FI_Today`. Lower ratio = you assume you can survive on less.                                                                                                                     |
| `coast_fi_real_return`  | `0.06`      | `0.04`      | Assumed compounding rate for Coast FI. A lower return significantly raises the amount of `Coast_FI_Today` you need right now to coast.                                                                                                    |
| `cape_swr_floor`        | `0.04`      | `0.03`      | Guyton-Klinger Guardrail. If the market crashes in the simulation, this is the lowest your withdrawal rate can go. A lower floor means you assume you can tighten your belt significantly, which**increases** survival probabilities. |
| `cape_swr_ceiling`      | `0.06`      | `0.05`      | Guyton-Klinger Guardrail. How high your spending can scale in a bull market. A higher ceiling increases lifestyle but slightly degrades long-term safety.                                                                                   |
| `human_capital_max_age` | `65.0`      | `50.0`      | The age you expect to stop earning. A lower age forces your `Target_FI` to shoulder the load sooner.                                                                                                                                      |

### 2. Capital Market Assumptions (`[assumptions.cma]`)

These define the baseline growth and volatility of your portfolio.

| Parameter                | Aggressive | Conservative | Impact on Metrics                                                                                                                                                                                                                  |
| :----------------------- | :--------- | :----------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `expected_real_return` | `0.07`   | `0.04`     | The average inflation-adjusted return. Directly controls the mean drift of the simulation. A lower return dramatically reduces `Wealth_P50` projections and lowers `Probability_Of_Success`.                                   |
| `fat_tail_multiplier`  | `1.0`    | `1.3`      | Inflates your historical volatility to simulate extreme Black Swan crashes using a Student-T distribution. Higher multiplier drastically increases sequence of returns risk (SoRR), punishing your `Runway_Months_Stressed_P10`. |

### 3. Monte Carlo Simulation Mechanics (`[assumptions.monte_carlo]`)

These parameters dictate the mathematical bounds of the 1,000+ simulation paths.

| Parameter                   | Aggressive  | Conservative | Impact on Metrics                                                                                                                                                                                      |
| :-------------------------- | :---------- | :----------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `iterations`              | `1000`    | `10000`    | Number of parallel futures generated. Higher iterations increase statistical confidence in the P10 (stressed) and P90 (favorable) outcomes but take longer to run.                                     |
| `annual_volatility`       | `0.12`    | `0.18`     | Base market volatility. Higher volatility creates wider spreads between your `Wealth_P10` and `Wealth_P90` outcomes.                                                                               |
| `real_return_floor`       | `-0.20`   | `-0.40`    | Absolute limit on how bad a single year can be in the simulation. A lower floor allows the jump-diffusion model to generate apocalyptic crashes, testing extreme resilience.                           |
| `desired_target_age`      | `85`      | `95`       | Sets the decumulation lifespan. A longer lifespan (95) requires the portfolio to survive more years, demanding a lower withdrawal rate and reducing `Probability_Of_Success` for early retirees.     |
| `sorr_cagr_window_months` | `36` (3y) | `60` (5y)  | The evaluation window for Sequence of Returns Risk metrics. A longer window demands portfolio durability over a longer initial retirement stress period, impacting `Decumulation_First_5Y_CAGR_P10`. |

### 4. Macro Regime Engine (`[assumptions.monte_carlo.markov_regime]`)

Simulates prolonged market environments (Bull, Bear, Stagflation) rather than static, independent year-over-year returns.

| Parameter             | Aggressive          | Conservative               | Impact on Metrics                                                                                                                                                                                                                              |
| :-------------------- | :------------------ | :------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `transition_matrix` | Biased to Bull      | Biased to Bear/Stagflation | Dictates the probability of entering and staying in adverse market regimes. A conservative matrix traps the simulation in prolonged Bear states, brutally dragging down `Terminal_Wealth_P50` and FI probability.                            |
| `state_stag`        | Low inflation spike | High inflation spike       | Determines drift, volatility, and inflation during stagflation. Conservative parameters assume extreme purchasing power erosion, increasing `Peak_Inflation_Experienced_Pct` and forcing equities to work harder to preserve your FI target. |

### 5. Human Capital & Income Shocks (`[assumptions.monte_carlo.human_capital]`)

Models job loss or zero-bonus years that are highly correlated to market crashes. Most calculators ignore this, assuming you keep saving perfectly during a recession.

| Parameter              | Aggressive    | Conservative   | Impact on Metrics                                                                                                                                                                                        |
| :--------------------- | :------------ | :------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `shock_probability`  | `0.05` (5%) | `0.30` (30%) | Chance of losing your savings capacity (`pmt = 0`) when the market hits Bear/Stagflation. A high probability severely tests your emergency fund, surfacing as massive `Lost_Savings_Expected_Value`. |
| `shock_duration_max` | `3` months  | `12`+ months | How long the simulated unemployment lasts. Longer durations halt your accumulation phase entirely, pushing out your `Months_To_FI_Aggressive_P10` significantly.                                       |

### 6. Algorithmic Glide Path / "Bond Tent" (`[assumptions.monte_carlo.glide_path]`)

Protects against Sequence of Returns Risk (SORR) by mechanically de-risking as you approach FIRE, and re-risking afterward.

| Parameter                     | Aggressive       | Conservative       | Impact on Metrics                                                                                                                                                                                      |
| :---------------------------- | :--------------- | :----------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `derisk_start_months_prior` | `24` (2 years) | `84` (7 years)   | How early you start shifting from equities to debt. A longer derisking period caps your overall accumulation ceiling (lowering `Terminal_Wealth_P50`) but heavily insulates you from pre-FI crashes. |
| `fi_target_equity_weight`   | `0.60`         | `0.30`           | Your exact equity exposure at the moment you FIRE. Lower means less volatility risk at the finish line, but demands a larger overall portfolio to survive decades of inflation.                        |
| `post_fi_re_risk_months`    | `60` (5 years) | `120` (10 years) | The period over which you slowly buy back into equities to fund your later years. Slow re-risking protects the fragile early retirement phase, improving `Decumulation_First_5Y_CAGR_P10`.           |
| `debt_real_return`          | `0.03`         | `0.01`           | The assumed real return of the non-equity portion of your portfolio during the Bond Tent. Lower return necessitates a significantly larger FI target.                                                  |
| `debt_volatility`           | `0.03`         | `0.05`           | The assumed volatility of the non-equity portion. Higher volatility risks bond-market crashes coinciding with equity crashes.                                                                          |

### 7. Guyton-Klinger Guardrails (`[assumptions.monte_carlo.guyton_klinger]`)

Dynamic withdrawal rules that alter your spending during retirement based on portfolio performance to ensure you don't run out of money.

| Parameter                      | Aggressive | Conservative | Impact on Metrics                                                                                                                                                                                    |
| :----------------------------- | :--------- | :----------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `withdrawal_upper_threshold` | `1.30`   | `1.15`     | Triggers a lifestyle cut if your withdrawal rate exceeds your initial SWR by this multiplier. A lower threshold forces cuts sooner during market dips, greatly enhancing `Probability_Of_Success`. |
| `withdrawal_lower_threshold` | `0.70`   | `0.85`     | Triggers a lifestyle raise if your withdrawal rate drops below initial SWR by this multiplier.                                                                                                       |
| `lifestyle_cut_multiplier`   | `0.95`   | `0.85`     | The severity of the spending cut when the upper threshold is breached. (e.g., 0.85 = 15% cut). Deeper cuts rescue the portfolio faster in worst-case scenarios, boosting `Terminal_Wealth_P10`.    |
| `lifestyle_raise_multiplier` | `1.05`   | `1.10`     | The generosity of the spending raise when the lower threshold is breached.                                                                                                                           |

### 8. Stochastic Inflation Model (`[assumptions.monte_carlo.inflation_model]`)

Uses an Ornstein-Uhlenbeck process to generate realistic, compounding inflation paths that revert to a mean.

| Parameter                | Aggressive | Conservative | Impact on Metrics                                                                                                                                                                    |
| :----------------------- | :--------- | :----------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mean_reversion_speed` | `0.3`    | `0.05`     | How fast an inflation spike returns to normal. A low speed means inflation stays painfully high for years, drastically increasing your required `Target_FI_Future_Nominal_P50`.    |
| `volatility_annual`    | `0.01`   | `0.03`     | The volatility of the inflation path. Higher volatility creates unpredictable purchasing power erosion.                                                                              |
| `max_inflation_cap`    | `0.10`   | `0.20`     | The absolute maximum inflation allowed. Raising this cap allows the model to simulate hyperinflation scenarios, which ruins purchasing power and slashes `Probability_Of_Success`. |

### 9. Jump-Diffusion Black Swans (`[assumptions.monte_carlo.jump_diffusion]`)

Merton Jump-Diffusion mechanics that inject catastrophic, instantaneous market crashes independent of standard volatility.

| Parameter                   | Aggressive | Conservative | Impact on Metrics                                                                                                                                                                 |
| :-------------------------- | :--------- | :----------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `jump_probability_annual` | `0.02`   | `0.10`     | The annual chance of a Black Swan event. A high probability severely punishes `Terminal_Wealth_P10` and ensures only the most robust portfolios survive the decumulation phase. |
| `jump_magnitude`          | `-0.15`  | `-0.35`    | The instant portfolio drop when a jump occurs. Massive negative magnitudes replicate events like 2008 or Black Monday, destroying `Runway_Months_Stressed_P10`.                 |
| `expense_ratio_drag`      | `0.002`  | `0.010`    | Annual portfolio fee drag. While small, compounded over 40+ years, a high fee drag secretly steals massive amounts of wealth, subtly eroding `Months_To_FI_Total_Base_P50`.     |

---

## Action Plan for a Resilient Future

If you are currently single and expecting potential marriage, kids, or career changes, it is highly recommended to use the **Conservative** configuration. This prevents the mathematical engine from giving you a false sense of security.

If the dashboard says you have a **90%+ Probability of Success** under the Conservative parameters, you are exceptionally well-positioned to handle whatever life throws at you.

**How to Apply:**
Edit the `financial_rules.toml` inside your repository according to the tables above.
The ETL pipeline will automatically read the updated `.toml`, parse it through `FinancialRules`, and pipe the exact parameters directly into the Numba Monte Carlo simulation and Polars vectorization engine at runtime.
