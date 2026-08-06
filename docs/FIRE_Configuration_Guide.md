# FIRE Forecasting Configuration Guide

The FIRE Forecasting engine computes your financial independence progress and models probabilities using stochastic Monte Carlo simulations and advanced risk vectors. Your configuration parameters heavily influence these calculations. 

Because life events (such as marriage, starting a family, or shifting careers) drastically alter both the capital required and your earning runway, the configuration should be adapted to mirror your current risk profile. 

This guide breaks down how to fine-tune the `financial_rules.toml` configuration to accommodate an aggressive (optimistic) FIRE approach versus a conservative (highly resilient) approach.

---

## The Two Profiles

### 1. The Aggressive (Optimistic) Profile
You assume strong market performance, fewer unplanned expenses, and high career stability. 
- **Goal:** Achieve FIRE numbers faster, assuming your lifestyle won't dramatically shift and your expenses stay near their baseline.
- **FI Probability:** Will model high because the simulation assumes fewer adverse shocks.

### 2. The Conservative (Resilient) Profile
Designed for younger individuals (e.g., a 26-year-old) who expect major life events (marriage, kids, healthcare costs) and anticipate economic headwinds. 
- **Goal:** Build an airtight "End Game" portfolio. The model will require significantly more wealth to show a "High Probability of Success."
- **FI Probability:** Harder to reach 95%+, but when you do, your portfolio is nearly invincible against sequence risk and fat-tailed market crashes.

---

## Key Parameters to Adjust

### 1. Core Withdrawal & Returns
These parameters dictate how fast you accumulate wealth and how much you need to stop working.

| Parameter | Aggressive | Conservative | What it does |
| :--- | :--- | :--- | :--- |
| `swr_multiplier` | `25.0` (4%) | `33.3` (3%) | Lower multiplier requires a much larger portfolio to consider you FI, creating a massive safety cushion for unknown future expenses (like marriage). |
| `coast_fi_real_return` | `0.06` | `0.04` | Conservative modeling assumes inflation eats into more of your investment growth while coasting. |
| `cape_swr_floor` | `0.04` | `0.035` | The withdrawal rate you would drop to in a severe market crash. A lower floor means you assume you will tighten your belt significantly more. |

### 2. Human Capital & Career Risk
Your human capital is your ability to earn. If you are 26, this is your biggest asset.

| Parameter | Aggressive | Conservative | What it does |
| :--- | :--- | :--- | :--- |
| `human_capital_max_age`| `65.0` | `55.0` | If conservative, assume you stop earning at 55 instead of 65. The model will force your investments to shoulder the load sooner. |
| `human_capital_discount_rate` | `0.04` | `0.06` | A higher discount rate assumes your future earnings are less reliable and therefore worth less today. |
| `career_volatility_risk_score` | `0.3` | `0.7` | Assuming high risk of job disruption requires a heavier reliance on liquid assets and passive income. |
| `upskilling_roi_multiplier_base` | `0.15` | `0.08` | Assume lower returns on any upskilling or salary bumps. |

### 3. Monte Carlo & Macrostochastic Engine
These parameters run the 10,000+ simulation paths to estimate sequence risk and probability of ruin.

| Parameter | Aggressive | Conservative | What it does |
| :--- | :--- | :--- | :--- |
| `desired_target_age` | `85` | `95` | A conservative approach assumes you live longer and therefore models a longer decumulation phase where your money cannot run out. |
| `max_months` | `480` (40 yrs) | `720` (60 yrs) | Required to match `desired_target_age`. If you are 26 and model to 86, use 720 months. |
| `annual_volatility` | `0.12` | `0.18` | Models much wider swings in your portfolio value during simulations. |
| `fat_tail_multiplier` | `1.1` | `1.3` | Forces the Monte Carlo simulation to generate more extreme, heavy market crashes (fat tails). |
| `stochastic_inflation_p90_multiplier` | `1.2` | `1.8` | Simulates high inflation environments that relentlessly compound your future lifestyle expenses. |

---

## Action Plan for a 26-Year-Old

If you are currently single and expecting potential marriage, kids, or career changes, it is highly recommended to use the **Conservative** configuration. This prevents the model from giving you a false sense of security.

If the model says you have a 90% chance of success under the Conservative parameters, you are exceptionally well-positioned to handle whatever life throws at you.

**How to Apply:**
Edit the `financial_rules.toml` inside your repository according to the table above. 
The ETL pipeline will automatically read the updated `.toml`, parse it through `FinancialRules`, and pipe the exact parameters into the Numba Monte Carlo simulation and Polars vectorization engine at runtime.
