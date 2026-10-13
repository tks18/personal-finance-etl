# Personal Finance ETL — Finance Features

> **Purpose:** expand Personal Finance ETL from financial reconstruction into stronger personal-finance, investment, risk, Tax, goal, and FIRE decision support.
>
> The roadmap deliberately offers a broad menu. **Deterministic finance remains authoritative. ML adds forecasting, probability, pattern detection, risk estimation, and personalized signals. AI stays last and read-only.**
>
> Existing transaction categorization is already mature and is not part of this roadmap.

---

# 1. Selection framework

Use this rule before implementing anything:

```text
Can financial rules calculate the correct answer exactly?
        │
       YES
        ↓
DETERMINISTIC
        │
       NO
        ↓
Does historical behaviour contain a learnable pattern?
        │
       YES
        ↓
ML / STATISTICAL MODEL
        │
       NO
        ↓
Is the remaining problem explanation or interaction?
        │
       YES
        ↓
AI / LLM
```

For every ML candidate, evaluate four dimensions:

| Dimension | Meaning |
| --- | --- |
| **Value** | How useful is it for real personal-finance decisions? |
| **Difficulty** | Engineering/model complexity |
| **Data fit** | Whether a personal-finance history is likely sufficient |
| **Recommendation** | Build, experiment, or defer |

ML should always retain:

```text
Model_Version
Training_Window
Feature_Version
Prediction_Date
Confidence / Interval
Backtest_Metric
Fallback_Model
```

---

# 2. Deterministic finance foundation

These features create the decision surfaces that ML can later enrich.

---

## FIN-FEAT-01 — Month-end financial close

**Priority:** High

Create one monthly close result from existing authorities:

```text
source freshness
+ cash reconciliation
+ investment reconciliation
+ Tax evidence quality
+ wealth state
        ↓
READY / REVIEW / BLOCKED
```

Include:

- cash residual;
- material reconciliation count;
- stale/missing evidence;
- `CHECK_REQUIRED` Tax events;
- changes since previous close.

**Why first:** it turns the system into a proper personal financial close process without inventing new financial truth.

---

## FIN-FEAT-02 — Wealth-change attribution

**Priority:** High

Explain:

```text
Opening Wealth
+ Net Savings
+ Market Movement
+ FX Movement
+ Realized / Distribution Effects
+ Reconciliation Adjustments
+ Tax-State Movement
= Closing Wealth
```

Keep an explicit `Unexplained_Difference`.

This becomes a powerful input for later ML trend and anomaly models.

---

## FIN-FEAT-03 — Cash runway and liquidity planner

**Priority:** High

Calculate:

```text
Cash Runway
Liquid-Asset Runway
Emergency-Fund Coverage
No-Income Runway
Stressed Runway
```

Run explicit deterministic scenarios such as income interruption or expense shock.

Liquidity stays separate from total net worth.

---

## FIN-FEAT-04 — Goal-based planning

**Priority:** High

Support multiple goals:

```text
emergency fund
house / down payment
vehicle
travel
education
major purchase
financial independence
retirement
```

For each:

```text
inflation-adjusted target
current funding
funding ratio
required monthly contribution
projected completion date
```

ML can later add completion probabilities.

---

## FIN-FEAT-05 — Tax-lot disposal simulator

**Priority:** High

Scenario input:

```text
Instrument
Quantity
Scenario Date
Scenario Price
Scenario FX
```

Return:

- FIFO lots consumed;
- holding periods;
- basis;
- hypothetical gain/loss;
- indicative Tax effect;
- remaining lots.

Scenario state must never mutate canonical FIFO.

---

## FIN-FEAT-06 — Tax-aware rebalance simulator

**Priority:** High

Use current lots, allocation, cash, target allocation, and Tax impact to propose deterministic rebalance deltas.

Order of preference:

```text
use new cash
→ fill underweights
→ avoid unnecessary sales
→ expose FIFO / Tax impact when sales are needed
```

No execution and no security-selection model.

---

## FIN-FEAT-07 — Concentration and diversification monitor

**Priority:** Medium–High

Measure exposure by:

- instrument;
- asset class;
- sector;
- geography;
- currency;
- broker/account;
- top-N holdings.

Metrics can include:

```text
Top-1
Top-5
HHI
configured allocation limit
deviation
```

---

## FIN-FEAT-08 — Drawdown and recovery analytics

**Priority:** Medium–High

Calculate:

```text
peak
trough
maximum drawdown
drawdown duration
recovery duration
current drawdown
```

At portfolio and useful subportfolio grains.

This becomes the deterministic baseline for ML downside-risk models.

---

## FIN-FEAT-09 — Deterministic stress library

**Priority:** Medium–High

Named shocks:

```text
income -30%
income = 0
expenses +20%
equity -35%
US equity -40%
INR depreciation +15%
inflation 8%
combined stagflation
```

Run through existing Wealth/FIRE engines using isolated scenario overlays.

---

## FIN-FEAT-10 — FIRE sensitivity matrix

**Priority:** Medium

Vary:

```text
savings rate
expenses
inflation
return assumptions
FI spending target
retirement age
equity allocation
```

Compare:

```text
months to FI
required corpus
success probability
terminal wealth
```

This shows which assumptions actually move the plan.

---

# 3. ML — Cash flow, spending and liquidity

---

## FIN-ML-01 — Multi-horizon cash-flow forecasting

**Value:** Very High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Forecast separately:

```text
income
core expense
discretionary expense
net cash flow
```

for:

```text
1 month
3 months
6 months
12 months
```

Benchmark:

1. seasonal naive;
2. weighted rolling baseline;
3. exponential smoothing;
4. regression with calendar/trend features;
5. more advanced models only if justified.

Use rolling time-series backtesting.

Output prediction intervals, not only point forecasts.

---

## FIN-ML-02 — Category-level expense forecasting

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Strong for established categories  
**Recommendation:** **Build**

Your categories are already robust, so model spending **within** them.

Forecast useful financial buckets:

```text
housing
food
travel
health
transport
utilities
discretionary
other recurring/core
```

Allow different models by category. Stable categories may need simple seasonality; volatile categories may need probabilistic intervals.

Use the output for budget planning and goal cash requirements.

---

## FIN-ML-03 — Spending change-point detection

**Value:** High  
**Difficulty:** Low–Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Detect structural changes such as:

```text
new spending baseline
persistent discretionary increase
expense compression
seasonal shift
new volatility regime
```

Start with statistical change-point detection rather than heavy ML.

Output:

```text
Category
Change_Date
Old_Level
New_Level
Magnitude
Confidence
```

Excellent input for month-end review.

---

## FIN-ML-04 — Lifestyle-inflation detection

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Model the relationship between:

```text
income growth
core-expense growth
discretionary growth
savings-rate movement
```

Detect cases where spending structurally expands after income rises.

Output:

```text
Income_Growth
Expense_Growth
Savings_Rate_Change
Lifestyle_Inflation_Score
Primary_Drivers
```

Start with deterministic ratios; use regression/change detection for richer trend estimation.

---

## FIN-ML-05 — Dynamic liquidity forecast

**Value:** Very High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Consume cash-flow forecasts and current liquid assets.

Estimate:

```text
P10 / P50 / P90 future cash
probability of breaching emergency buffer
expected minimum cash
likely breach window
```

This turns the deterministic runway into forward-looking liquidity risk.

The emergency-buffer threshold remains deterministic.

---

## FIN-ML-06 — Large-expense probability model

**Value:** Medium–High  
**Difficulty:** Medium  
**Data fit:** Depends on history  
**Recommendation:** **Experiment**

Estimate probability/range of irregular large expenses over the next:

```text
3 months
6 months
12 months
```

Use historical irregular expenses, seasonality, category, and timing.

Do not predict exact purchases. Estimate financial exposure.

Useful for liquidity reserves and goal planning.

---

## FIN-ML-07 — Spending volatility model

**Value:** Medium  
**Difficulty:** Low–Medium  
**Data fit:** Strong  
**Recommendation:** **Build if useful**

Estimate how predictable each spending bucket is.

Output:

```text
Expected_Monthly
Volatility
P10
P90
Predictability_Status
```

This helps distinguish categories suitable for fixed budgets from categories needing buffers.

---

# 4. ML — Savings, goals and financial planning

---

## FIN-ML-08 — Savings-rate forecast

**Value:** Very High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Forecast:

```text
income
expenses
savings
savings rate
```

Use the distribution rather than one point estimate.

Feed it into goal and FIRE planning instead of assuming the latest savings rate continues forever.

---

## FIN-ML-09 — Goal completion probability

**Value:** Very High  
**Difficulty:** Medium  
**Data fit:** Strong once goals exist  
**Recommendation:** **Build**

For every deterministic goal:

```text
current funded amount
forecast contribution
target date
target amount
inflation
investment uncertainty
```

Estimate:

```text
Probability_On_Time
Expected_Completion_Date
P10 / P50 / P90 completion
Required_Contribution_Adjustment
```

The deterministic funding ratio remains the baseline.

---

## FIN-ML-10 — Contribution-capacity forecast

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Estimate how much money is realistically available for future investing after:

```text
expected income
expected spending
known goals
liquidity buffer
Tax reserve
```

Output:

```text
Expected_Investable_Cash
Conservative_Investable_Cash
Aggressive_Investable_Cash
```

This connects household forecasting directly to portfolio planning.

---

## FIN-ML-11 — Goal-priority stress model

**Value:** Medium–High  
**Difficulty:** Medium  
**Data fit:** Good  
**Recommendation:** **Experiment**

When projected cash cannot fund every goal, estimate which goals are most likely to slip under current behaviour.

Do not let ML decide priorities.

User-configured goal priority remains authoritative.

ML estimates **risk of missing each goal**.

---

## FIN-ML-12 — Financial trajectory clustering

**Value:** Medium  
**Difficulty:** Medium  
**Data fit:** Depends on history length  
**Recommendation:** **Experiment**

Identify historical periods such as:

```text
high savings / low spending
income expansion
lifestyle inflation
expense stress
investment acceleration
cash compression
```

Use transparent clustering over monthly financial-state features.

This can provide context for current behaviour without assigning moral labels.

---

# 5. ML — Investment risk and portfolio management

---

## FIN-ML-13 — Portfolio risk-regime detection

**Value:** High  
**Difficulty:** Medium–High  
**Data fit:** Strong from market history  
**Recommendation:** **Experiment → Build if useful**

Inputs:

```text
realized volatility
drawdown
cross-asset correlation
FX volatility
benchmark dispersion
```

Start with transparent clustering.

Evaluate Hidden Markov Models only if regime persistence adds decision value.

Output:

```text
Current_Risk_Regime
Confidence
Regime_Characteristics
```

Do not automatically change allocation.

---

## FIN-ML-14 — Drawdown probability estimation

**Value:** High  
**Difficulty:** Medium–High  
**Data fit:** Strong from market history  
**Recommendation:** **Experiment**

Estimate:

```text
P(drawdown > 10%)
P(drawdown > 20%)
expected downside range
expected recovery range
```

for a defined horizon.

Use current portfolio exposures and historical risk behaviour.

This is downside-risk estimation, not price prediction.

---

## FIN-ML-15 — Correlation-regime monitoring

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build / Experiment**

Diversification often weakens when correlations rise.

Track changing relationships between:

```text
Indian equity
US equity
debt
gold / other assets if present
FX
benchmarks
```

Detect statistically meaningful correlation shifts.

Surface:

```text
Normal
Elevated
Concentrated-Risk
```

Use it as a portfolio review signal.

---

## FIN-ML-16 — Allocation-drift forecast

**Value:** Medium–High  
**Difficulty:** Medium  
**Data fit:** Good  
**Recommendation:** **Experiment**

Estimate how current allocation is likely to drift under:

- expected contributions;
- historical return distributions;
- no rebalancing.

Output probability of breaching configured allocation bands within a horizon.

Useful for planning **when** a rebalance may become necessary without timing the market.

---

## FIN-ML-17 — Contribution allocation optimizer

**Value:** High  
**Difficulty:** Medium–High  
**Data fit:** Good  
**Recommendation:** **Experiment**

Instead of selling to rebalance, determine how future contributions could reduce allocation drift.

Start deterministic.

Then use optimization / probabilistic scenarios to evaluate contribution allocation under uncertain returns.

Objective examples:

```text
minimize expected target deviation
minimize probability of band breach
avoid taxable sales
```

This is more useful than predicting which security will outperform.

---

## FIN-ML-18 — Portfolio downside-driver model

**Value:** Medium–High  
**Difficulty:** Medium  
**Data fit:** Good  
**Recommendation:** **Experiment**

Estimate which exposures contribute most to downside risk under current portfolio state.

Features:

```text
asset weights
historical volatility
correlation
FX exposure
drawdown sensitivity
```

Output ranked risk contributors with transparent contribution estimates.

Avoid black-box portfolio scores.

---

## FIN-ML-19 — Benchmark-relative performance regime

**Value:** Medium  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Experiment**

Detect periods where active performance relative to shadow benchmarks is:

```text
persistently positive
neutral
persistently negative
highly unstable
```

This is descriptive regime analysis, not an expected-alpha predictor.

---

## FIN-ML-20 — FX-risk forecast

**Value:** Medium–High for foreign holdings  
**Difficulty:** Medium–High  
**Data fit:** Strong external history  
**Recommendation:** **Experiment**

Estimate distribution of FX contribution to portfolio risk over a chosen horizon.

Output:

```text
expected FX volatility
P(adverse FX move > threshold)
portfolio INR sensitivity
```

Do not forecast an exact USD/INR price target.

---

# 6. ML — FIRE and retirement planning

---

## FIN-ML-21 — FIRE parameter calibration research mode

**Value:** High for model research  
**Difficulty:** Medium  
**Data fit:** Strong external history  
**Recommendation:** **Build as research-only**

Estimate candidate:

- volatility;
- correlation;
- inflation dynamics;
- regime persistence;
- jump frequency.

Output:

```text
Suggested_Value
Current_Config_Value
Historical_Window
Method
Uncertainty
```

Never write directly to FinancialRules.

---

## FIN-ML-22 — Dynamic savings-path model for FIRE

**Value:** Very High  
**Difficulty:** Medium  
**Data fit:** Strong  
**Recommendation:** **Build**

Replace the simplistic assumption that current savings behaviour remains constant with a forecast distribution derived from:

```text
income trajectory
expense trajectory
historical savings
known goals
life-stage trend
```

Feed the distribution into FIRE scenarios.

This is one of the strongest ML integrations because human savings behaviour materially affects FI timing.

---

## FIN-ML-23 — Human-capital income-risk model

**Value:** High  
**Difficulty:** Medium–High  
**Data fit:** Personal history may be limited  
**Recommendation:** **Experiment cautiously**

Estimate uncertainty around future income growth/interruption.

Because one person's employment history is small, combine:

- deterministic user scenarios;
- personal income trend;
- configurable external assumptions.

ML should enrich, not replace, the existing human-capital shock model.

---

## FIN-ML-24 — FIRE outcome surrogate model

**Value:** Medium  
**Difficulty:** High  
**Data fit:** Generated simulation data is abundant  
**Recommendation:** **Optional experiment**

Train a lightweight model on Monte Carlo outputs to approximate:

```text
success probability
months to FI
terminal wealth percentile
```

from scenario parameters.

Why?

Not to replace Monte Carlo, but to enable extremely fast interactive sensitivity exploration.

The canonical answer still comes from the real simulation.

---

## FIN-ML-25 — Sequence-of-returns risk classifier

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Strong simulated data  
**Recommendation:** **Experiment**

Use simulated paths to identify combinations of early-retirement conditions associated with failure:

```text
early drawdown
high inflation
withdrawal pressure
low bond buffer
employment / income shock
```

Output interpretable risk drivers.

This can make FIRE failure modes easier to understand without changing the simulation.

---

# 7. ML — Tax and cash planning

---

## FIN-ML-26 — Tax cash-requirement forecast

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Good  
**Recommendation:** **Build**

Forecast future **cash reserve need for Tax**, not statutory liability.

Consume:

```text
known TaxEvents
income forecast
realized investment activity
historical Tax cash timing
```

Output:

```text
Expected_Tax_Cash_Need
P10
P50
P90
Evidence_Coverage
```

The Tax Engine remains authoritative for known Tax evidence.

---

## FIN-ML-27 — Realization / Tax exposure scenario distribution

**Value:** Medium–High  
**Difficulty:** Medium–High  
**Data fit:** Good  
**Recommendation:** **Experiment**

Use current unrealized positions plus deterministic sale scenarios to estimate potential Tax exposure ranges under different realization amounts.

This is scenario modelling, not a model deciding what to sell.

---

# 8. ML — Integrated personal-finance intelligence

---

## FIN-ML-28 — Financial early-warning system

**Value:** Very High  
**Difficulty:** Medium  
**Data fit:** Strong once upstream features exist  
**Recommendation:** **Build late**

Combine signals from:

```text
cash runway
savings forecast
spending acceleration
goal slippage
portfolio concentration
drawdown risk
Tax cash requirement
reconciliation state
```

Start with deterministic rules.

Only learn weights later if enough historical outcomes exist.

Output:

```text
HEALTHY
WATCH
ACTION_REQUIRED
```

plus explicit drivers.

No opaque 0–100 score without explanation.

---

## FIN-ML-29 — Personal financial resilience model

**Value:** High  
**Difficulty:** Medium–High  
**Data fit:** Good after scenario features exist  
**Recommendation:** **Experiment**

Estimate resilience under combinations of:

```text
income interruption
expense shock
market drawdown
inflation
FX shock
Tax cash need
```

Use deterministic stress scenarios to generate training/evaluation data.

Output resilience dimensions rather than one mysterious score:

```text
Liquidity_Resilience
Savings_Resilience
Portfolio_Resilience
Goal_Resilience
FIRE_Resilience
```

---

## FIN-ML-30 — Decision-impact ranking

**Value:** High  
**Difficulty:** Medium  
**Data fit:** Strong from scenario engine  
**Recommendation:** **Experiment**

Given the current financial state, rank which controllable variables have the greatest impact:

```text
increase savings
reduce discretionary spending
increase contributions
delay goal
change retirement age
change allocation within configured choices
```

Use deterministic sensitivity/scenario outputs as the truth source.

ML can approximate/rank impacts for fast exploration.

This is much safer and more useful than predicting stock returns.

---

# 9. AI — optional final layer

AI only becomes useful after these structured outputs exist.

---

## FIN-AI-01 — Personal-finance explainer

Explain:

- wealth movement;
- liquidity;
- savings trajectory;
- goal risk;
- portfolio risk;
- FIRE changes;
- Tax cash needs.

Every answer should point to the underlying metrics.

---

## FIN-AI-02 — Investment review assistant

Explain:

- allocation;
- concentration;
- drawdown;
- benchmark-relative performance;
- FX;
- Tax-lot scenarios;
- ML risk signals.

No autonomous trading recommendations.

---

## FIN-AI-03 — Goal / FIRE planning assistant

Compare scenarios and explain which assumptions drove the outcome.

Numbers remain owned by deterministic/ML engines.

---

## FIN-AI-04 — Tax evidence assistant

Explain known Tax evidence, cash-planning forecasts, and review gaps.

No final statutory liability.

---

# 10. Best ML shortlist

If only a small number of ML capabilities are implemented, start here:

| Rank | Feature | Why |
| ---: | --- | --- |
| **1** | Multi-horizon cash-flow forecasting | Directly useful across budgeting, liquidity, goals and FIRE |
| **2** | Dynamic liquidity forecast | Turns cash management into forward-looking risk |
| **3** | Savings-rate forecast | Strong bridge from household behaviour to FIRE |
| **4** | Goal completion probability | Makes goal planning probabilistic and actionable |
| **5** | Spending change-point detection | High value with existing clean categories |
| **6** | Dynamic FIRE savings-path model | Improves one of FIRE's most personal assumptions |
| **7** | Portfolio risk-regime detection | Useful investment-risk signal without predicting prices |
| **8** | Correlation-regime monitoring | Directly tests whether diversification is weakening |
| **9** | Tax cash-requirement forecast | Practical cash-management value |
| **10** | Financial early-warning system | Powerful once the upstream signals exist |

---

# 11. Suggested experimentation tiers

## Tier A — high-value, realistic personal data

```text
cash-flow forecasting
category-level expense forecasting
spending change detection
lifestyle-inflation detection
liquidity forecasting
savings-rate forecasting
goal probability
Tax cash planning
```

## Tier B — investment / market-history models

```text
risk regimes
drawdown probability
correlation regimes
allocation drift
FX risk
benchmark-relative regimes
```

## Tier C — simulation-powered models

```text
FIRE surrogate
sequence-risk classifier
resilience model
decision-impact ranking
```

These can use generated Monte Carlo/scenario data, so training-data scarcity is less severe.

---

# 12. Final roadmap

```text
DETERMINISTIC FOUNDATION
month-end close
wealth attribution
cash runway
goals
Tax-lot / rebalance
concentration
drawdown
stress
FIRE sensitivity
        ↓
ML — HOUSEHOLD
cash-flow
expense forecasts
change detection
lifestyle inflation
liquidity
savings
        ↓
ML — GOALS
goal probability
contribution capacity
goal stress
        ↓
ML — INVESTMENTS
risk regimes
drawdown risk
correlation
allocation drift
contribution optimization
FX risk
        ↓
ML — FIRE / TAX
dynamic savings path
parameter calibration
sequence risk
Tax cash forecast
        ↓
ML — INTEGRATED
early warning
resilience
decision-impact ranking
        ↓
AI — LAST
explain and navigate the intelligence
```

The target is not to make Personal Finance ETL an “AI finance app.”

The target is much more useful:

> **Turn the clean financial history already produced by the system into forecasts, probabilities, risk signals, and decision support that deterministic accounting alone cannot provide.**
