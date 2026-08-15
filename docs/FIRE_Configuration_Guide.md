# 🔥 FIRE Forecasting Configuration Guide

> [!IMPORTANT]
> The FIRE Forecasting engine computes your financial independence progress, sequence of returns risk (SoRR), and runway survival using a compiled Numba stochastic Monte Carlo simulation. **Your configuration parameters heavily dictate the realism of these calculations.**

Because life events drastically alter both the capital required and your earning runway, the configuration must be brutally honest and adapted to mirror your true risk profile. 

This guide breaks down how to fine-tune the `financial_rules.toml` configuration to accommodate an **Aggressive (Optimistic)** approach versus a **Conservative (Highly Resilient)** approach, detailing exactly how each parameter affects your downstream quantitative metrics.

---

## 🎭 The Two Profiles

### 1. The Aggressive (Optimistic) Profile
You assume strong market performance, fewer unplanned expenses, and high career stability. 

*   **Goal:** Achieve FIRE numbers faster, assuming your lifestyle won't dramatically shift and your expenses stay near their baseline.
*   **Impact on Dashboard:** `Probability_Of_Success_Pct` will model high. `Runway_Months` will stretch further, assuming minimal turbulence.

### 2. The Conservative (Resilient) Profile
Designed for individuals who expect major life events (marriage, kids, healthcare costs) and anticipate economic headwinds. 

*   **Goal:** Build an airtight "End Game" portfolio. The model will require significantly more wealth to show a "High Probability of Success."
*   **Impact on Dashboard:** `Probability_Of_Success_Pct` is harder to reach 95%+, but when you do, your portfolio is mathematically invincible against fat-tailed market crashes.

---

## ⚙️ Key Parameters & Their Quantitative Impact

### 1. Core Withdrawal & FIRE Rules (`[assumptions.fire]`)
These parameters dictate the velocity at which you accumulate wealth and the absolute capital required to stop working.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `swr_multiplier` | `25.0` (4%) | `33.3` (3%) | Determines your absolute `Target_FI_Today`. A lower SWR (higher multiplier) drastically increases capital required, lowering your early `Probability_Of_Success_Pct`. |
| `lean_fi_ratio` | `0.75` | `0.60` | Multiplier on Target FI for pure survival mode. Lower ratio = you assume you can survive on significantly less. |
| `coast_fi_real_return` | `0.06` | `0.04` | Assumed compounding rate for Coast FI. A lower return significantly raises the `Coast_FI_Today` required right now. |
| `cape_swr_floor` | `0.04` | `0.03` | **Guyton-Klinger Guardrail.** The lowest your withdrawal rate can go during a simulated crash. A lower floor *increases* survival probabilities by assuming you can tighten your belt. |
| `cape_swr_ceiling` | `0.06` | `0.05` | **Guyton-Klinger Guardrail.** How high your spending scales in a bull market. A higher ceiling increases lifestyle but slightly degrades long-term safety. |
| `human_capital_max_age` | `65.0` | `50.0` | The age you expect to stop earning. A lower age forces your `Target_FI` to shoulder the load sooner. |

### 2. Capital Market Assumptions (`[assumptions.cma]`)
Defines the baseline growth and extreme volatility of your portfolio.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `expected_real_return` | `0.07` | `0.04` | The average inflation-adjusted return. Directly controls mean drift. A lower return dramatically reduces `Wealth_P50` projections. |
| `fat_tail_multiplier` | `1.0` | `1.3` | Inflates historical volatility to simulate Black Swan crashes via Student-T distribution. Higher multiplier drastically increases Sequence of Returns Risk (SoRR). |

### 3. Monte Carlo Simulation Mechanics (`[assumptions.monte_carlo]`)
Dictates the mathematical rigor of the 1,000+ simulation paths.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `iterations` | `1000` | `10000` | Number of parallel futures. Higher iterations increase statistical confidence in the P10 (stressed) outcomes but take longer to compute. |
| `annual_volatility` | `0.12` | `0.18` | Base market volatility. Wider volatility creates massive spreads between `Wealth_P10` and `Wealth_P90`. |
| `real_return_floor` | `-0.20` | `-0.40` | Absolute limit on a single bad year. A lower floor allows the jump-diffusion model to generate apocalyptic crashes. |
| `desired_target_age` | `85` | `95` | Sets the decumulation lifespan. A longer lifespan demands a lower withdrawal rate, reducing early FI probability. |
| `sorr_cagr_window_months`| `36` (3y) | `60` (5y) | The evaluation window for Sequence of Returns Risk. Longer windows demand portfolio durability over prolonged initial stress. |

### 4. Macro Regime Engine (`[assumptions.monte_carlo.markov_regime]`)
Simulates prolonged market environments (Bull, Bear, Stagflation) rather than static year-over-year returns.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `transition_matrix` | Biased to Bull | Biased to Bear | Dictates the probability of entering adverse regimes. A conservative matrix traps the simulation in prolonged Bear states, dragging down `Terminal_Wealth_P50`. |
| `state_stag` | Low inflation | High inflation | Determines drift and volatility during stagflation. Conservative parameters assume extreme purchasing power erosion, forcing equities to work harder. |

### 5. Human Capital & Income Shocks (`[assumptions.monte_carlo.human_capital]`)
Models job loss or zero-bonus years that are strictly correlated to market crashes.

> [!WARNING]  
> Most calculators ignore this, assuming you keep saving perfectly during a recession. We test pure survival mode.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `shock_probability` | `0.05` (5%) | `0.30` (30%) | Chance of losing savings capacity (`pmt = 0`) when the market hits Bear/Stagflation. High probability severely tests your emergency fund. |
| `shock_duration_max` | `3` months | `12`+ months | How long simulated unemployment lasts. Longer durations halt accumulation, pushing out your `Months_To_FI_Aggressive_P10`. |

### 6. Algorithmic Glide Path / "Bond Tent" (`[assumptions.monte_carlo.glide_path]`)
Protects against Sequence of Returns Risk (SORR) by mechanically de-risking as you approach FIRE, and re-risking afterward.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `derisk_start_months_prior`| `24` (2 years) | `84` (7 years) | How early you shift to debt. Longer periods cap overall accumulation (lowering `Terminal_Wealth_P50`) but insulate from pre-FI crashes. |
| `fi_target_equity_weight` | `0.60` | `0.30` | Your exact equity exposure at the moment you FIRE. Lower means less volatility risk at the finish line, but requires a larger portfolio. |
| `post_fi_re_risk_months` | `60` (5 years) | `120` (10 years) | The period over which you slowly buy back into equities. Slow re-risking protects the fragile early retirement phase. |
| `debt_real_return` | `0.03` | `0.01` | Assumed real return of the non-equity portion during the Bond Tent. Lower return necessitates a significantly larger FI target. |
| `debt_volatility` | `0.03` | `0.05` | Assumed volatility of the non-equity portion. Higher volatility risks bond-market crashes coinciding with equity crashes. |

### 7. Guyton-Klinger Guardrails (`[assumptions.monte_carlo.guyton_klinger]`)
Dynamic withdrawal rules that alter your spending during retirement based on portfolio performance.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `withdrawal_upper_threshold`| `1.30` | `1.15` | Triggers a lifestyle cut if withdrawal rate exceeds initial SWR by this multiplier. Lower thresholds force cuts sooner, greatly enhancing `Probability_Of_Success`. |
| `withdrawal_lower_threshold`| `0.70` | `0.85` | Triggers a lifestyle raise if your withdrawal rate drops below initial SWR by this multiplier. |
| `lifestyle_cut_multiplier` | `0.95` | `0.85` | The severity of the spending cut (e.g., 0.85 = 15% cut). Deeper cuts rescue the portfolio faster in worst-case scenarios. |
| `lifestyle_raise_multiplier`| `1.05` | `1.10` | The generosity of the spending raise when the lower threshold is breached in a raging bull market. |

### 8. Stochastic Inflation Model (`[assumptions.monte_carlo.inflation_model]`)
Uses an Ornstein-Uhlenbeck process to generate realistic, compounding inflation paths that revert to a mean.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `mean_reversion_speed` | `0.3` | `0.05` | How fast an inflation spike returns to normal. Low speed means inflation stays high, drastically increasing `Target_FI_Future_Nominal_P50`. |
| `volatility_annual` | `0.01` | `0.03` | The volatility of the inflation path. Higher volatility creates unpredictable purchasing power erosion. |
| `max_inflation_cap` | `0.10` | `0.20` | Raising this cap allows the model to simulate hyperinflation scenarios, slashing `Probability_Of_Success`. |

### 9. Jump-Diffusion Black Swans (`[assumptions.monte_carlo.jump_diffusion]`)
Merton Jump-Diffusion mechanics that inject catastrophic, instantaneous market crashes independent of standard volatility.

| Parameter | Aggressive | Conservative | Institutional Impact |
| :--- | :--- | :--- | :--- |
| `jump_probability_annual` | `0.02` | `0.10` | The annual chance of a catastrophic Black Swan event. High probability severely punishes `Terminal_Wealth_P10`. |
| `jump_magnitude` | `-0.15` | `-0.35` | The instant portfolio drop when a jump occurs. Massive magnitudes replicate 2008, destroying `Runway_Months_Stressed_P10`. |
| `expense_ratio_drag` | `0.002` | `0.010` | Annual portfolio fee drag. Compounded over 40+ years, a high fee drag secretly steals massive amounts of wealth. |

---

## 🛡️ Action Plan for a Resilient Future

> [!TIP]
> If you are currently single and expecting potential marriage, kids, or career changes, it is **highly recommended** to use the **Conservative** configuration. This prevents the mathematical engine from giving you a false sense of security.

If the dashboard says you have a **90%+ Probability of Success** under the Conservative parameters, you are exceptionally well-positioned to handle whatever life throws at you.

**How to Apply:**  
Edit the `financial_rules.toml` inside your repository. The ETL pipeline will automatically parse it through `FinancialRules`, piping the parameters directly into the Numba Monte Carlo simulation and Polars vectorization engine at runtime.
