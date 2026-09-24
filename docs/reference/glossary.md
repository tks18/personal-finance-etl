# Glossary

This glossary defines the architectural, financial, analytical, and project-specific terminology used throughout Personal Finance ETL.

The goal is not to define every general finance or Python term.

It focuses on words whose meaning matters to understanding this implementation.

---

## Architecture & data engineering

## Analytical warehouse

The DuckDB persistence layer containing Bronze, Silver, Gold, and Meta schemas/contracts.

It is separate from the SQLite Raw Document Store.

---

## Bronze

Persistent **source-shaped analytical state** inside DuckDB.

Bronze is synchronized according to source semantics:

- reference/current-state sources can use full replacement,
- historical/event sources can use file-aware replacement.

Bronze is not the canonical financial model.

---

## Canonical contract

A stable financial/data concept exposed downstream after source-specific structure has been resolved.

Examples:

- canonical income transaction,
- canonical investment purchase,
- canonical benchmark observation.

Canonical contracts prevent downstream engines from depending on source layouts.

---

## Canonical financial model

The Silver-layer financial vocabulary and related in-memory analytical contracts used by downstream engines.

It represents concepts such as income, expenses, transfers, assets, investments, benchmarks, and tax lots.

---

## Change detection

The process of deciding whether a known source artifact requires reprocessing.

The Raw Store records SHA-256 fingerprints, while per-file-type configuration controls rehash policy for existing sources.

---

## Data contract

An explicit agreement describing a dataset's:

```text
purpose
layer
domain
grain
producer
inputs
fields
consumers
caveats
```

---

## Deterministic rebuild

Reconstructing derived state from complete upstream state, current rules/configuration, and current analytical code rather than incrementally patching every downstream dependency.

Silver and Gold follow this model.

---

## File-aware replacement

Bronze synchronization strategy for historical/event sources.

Rows owned by a changed source artifact are replaced while unrelated source history remains intact.

---

## Gold

The curated **decision-support serving layer** in DuckDB.

The current v6 architecture contains 17 physical Gold marts.

Gold is multi-grain and intentionally does not expose every intermediate calculation.

---

## Grain

What one row in a dataset represents.

Examples:

```text
Month
Month × Asset
Date × ISIN
Date × ISIN × Tax Lot
```

Grain determines valid joins, aggregation, and metric interpretation.

---

## Lineage

Information that connects analytical state back to its source or producer.

Current Bronze lineage includes source identity such as `__file_name__`.

---

## Meta

The DuckDB operational/control catalog.

Current v6 Meta tables capture source registry context, run telemetry, row counts, FinancialRules, and Settings.

---

## Raw Document Store / Raw Store

The SQLite persistence layer containing source registry state, synchronization state, fingerprints, and binary source payloads.

It is a provenance and recovery boundary, not an analytical mart.

---

## Raw artifact

A persisted source object before canonical analytical interpretation.

Can be:

- a physical file,
- or a virtual artifact such as benchmark-history Parquet bytes.

---

## Reference source

A source whose useful Bronze contract is its complete current state rather than accumulated historical event partitions.

---

## Silver

The **canonical financial and analytical contract layer** in DuckDB.

The current v6 architecture contains 20 physical Silver tables.

Silver is rebuilt deterministically.

---

## Source-shaped

Data that still reflects the structure/vocabulary of its originating source rather than the canonical financial model.

Bronze can intentionally remain source-shaped.

---

## Virtual artifact

A source artifact created by the application rather than discovered as a physical local file.

Current example: fetched benchmark history serialized to Parquet bytes and registered under a `virtual://...` identity.

---

## Ingestion & runtime

## `PENDING_BRONZE`

Raw Store synchronization state indicating that an artifact exists in Raw but still requires successful Bronze synchronization.

---

## `SYNCED`

Raw Store synchronization state indicating successful extraction and Bronze persistence for the artifact.

---

## Application-coordinated transaction

The orchestrator-managed lifecycle that begins/commits/rolls back local DuckDB and SQLite transactions.

It is **not** formal distributed two-phase commit.

---

## Backend facade

The application-facing boundary represented by `PersonalFinanceEngine`.

It allows CLI/desktop/headless surfaces to invoke backend capabilities without owning pipeline internals.

---

## Child-process execution

Running heavy ETL/analytics work outside the interactive frontend process.

Used to improve responsiveness and failure isolation.

---

## Extractor

Source-aware logic that converts persisted raw bytes into source-shaped analytical frames.

An extractor understands source format; it should not define downstream household finance.

---

## Full replacement

Bronze synchronization strategy where the complete current representation of a reference/current-state source is replaced when it changes.

---

## Headless execution

Running the backend pipeline without the normal interactive UI flow.

Useful for automation/scheduling.

---

## Idempotent source synchronization

Property that reprocessing the same unchanged source should not blindly duplicate persistent Bronze history.

---

## Snapshot

A point-in-time copy/protection mechanism for the analytical DuckDB state.

Different from Raw persistence, which protects source evidence.

---

## Household finance

## Active income

Income classified as active under FinancialRules.

Its exact category membership is policy-driven.

---

## After-tax market net worth

Household market wealth adjusted using modelled investment tax exposure where applicable.

It is a planning/modelled value rather than guaranteed liquidation proceeds.

---

## Asset

A canonical household balance-sheet resource.

Assets can carry semantics such as liquid, illiquid, cash pool, or investment.

---

## Book net worth

Net worth derived from reconstructed ledger/accounting balances.

Distinct from market-adjusted net worth.

---

## Cash expense

Expense classified as consuming cash under FinancialRules.

---

## Cash income

Income classified as cash-generating under FinancialRules.

---

## Cash pool

An asset configured as part of the household cash-balance boundary used for direct cash-flow reconciliation.

---

## Core expense

Expense classified as baseline/core spending under FinancialRules.

Used in planning perspectives such as Lean FI.

---

## Internal transfer

Movement between household-controlled assets that should not be interpreted as external income or expense.

---

## Liability

A household financial obligation subtracted from assets in net-worth calculation.

---

## Liquid asset

Asset classified as readily available for liquidity/runway purposes.

---

## Market net worth

Household net worth after incorporating market-derived investment valuation.

---

## Non-cash expense

Expense recognized financially without equivalent current cash outflow.

---

## Non-cash income

Income recognized financially without equivalent current cash inflow.

---

## Opening balance

Initial asset state used when complete lifetime transaction history is not represented inside the platform.

It is state initialization, not income.

---

## Organic growth

Asset/wealth growth attributed to appreciation or other non-contribution effects rather than direct savings/contributions.

---

## Savings contribution

Portion of asset/wealth growth attributed to household contributions/savings rather than organic market growth.

---

## Transfer

Movement of value between assets.

Transfers remain distinct from income and expense.

---

## Unified ledger

Normalized household activity model combining opening balances, income, expenses, and transfers into one financial state reconstruction path.

---

## Cash flow

## Operating cash flow

Cash movement classified as operating household activity under FinancialRules.

---

## Investing cash flow

Cash movement classified as investment-related activity.

---

## Financing cash flow

Cash movement classified as financing-related activity.

---

## Calculated net cash flow

Cash movement implied by classified operating, investing, financing, and transfer activity.

---

## Net cash movement

Observed change in configured cash-pool balances:

```text
Closing Cash - Opening Cash
```

---

## Unreconciled difference

Difference between observed cash movement and calculated classified cash flow.

A non-zero value is a reconciliation signal.

---

## Investment accounting

## ISIN

International Securities Identification Number.

Used as a stable instrument identity in the current investment model.

---

## Tax lot

A distinct investment acquisition unit carrying its own purchase date, quantity, cost basis, holding period, and tax state.

---

## FIFO

First-In, First-Out disposal accounting.

Sales consume the oldest available active investment lots first.

---

## Partial lot disposal

Sale/redemption that consumes only part of a tax lot, leaving the remaining quantity active with its original acquisition context.

---

## Cost basis

Investment cost associated with a lot or position for return/tax analysis.

---

## Broker reconciliation

Process of comparing transaction-reconstructed investment state with broker-reported current state and adjusting the analytical inventory when they disagree.

Design principle:

> Transactions explain history; broker state anchors current truth.

---

## Reconciliation lot / adjustment inventory

Mechanically introduced/adjusted inventory used to reconcile transaction-derived position state with broker-reported state.

Such adjustments can complicate historical tax interpretation.

---

## Market value

Current economic value of an investment position based on market observations.

---

## Realized gain / loss

Investment profit/loss created by an actual disposal.

---

## Unrealized gain / loss

Investment profit/loss implied by current market value while the position remains active.

---

## Holding period

Elapsed time between acquisition and the relevant current/sale date used for tax classification.

---

## Long-term / short-term classification

Tax treatment based on instrument type and holding period under the implemented jurisdictional rules.

---

## Benchmark analytics

## Benchmark

Reference market/index used to evaluate investment performance.

---

## Shadow benchmark portfolio

Synthetic benchmark position created using the same economic capital deployment as the real investment.

Purchases create benchmark-equivalent exposure; partial disposals reduce shadow exposure proportionally.

---

## Benchmark lag

Analytical context describing timing/coverage differences between investment state and available benchmark observations.

---

## Investment returns

## CAGR

Compound annual growth rate.

Point-to-point annualized growth measure.

Does not inherently account for irregular intermediate cash flows.

---

## XIRR

Annualized internal rate of return for irregular dated cash flows.

Used for cash-flow-aware investment performance.

---

## After-tax XIRR

XIRR calculated using tax-aware terminal state rather than one blanket tax-rate adjustment to pre-tax return.

---

## Benchmark XIRR

Cash-flow-aware XIRR of the shadow benchmark portfolio.

---

## Active return

Investment performance relative to the configured benchmark methodology.

Interpretation depends on grain and underlying return measure.

---

## Absolute return

Non-annualized return comparing value with invested/cost state.

Distinct from CAGR and XIRR.

---

## Max drawdown

Largest peak-to-trough decline over the relevant analytical value path.

Primary risk metric retained in the current v6 Gold serving contract.

---

## Portfolio XIRR

XIRR calculated from portfolio-level dated cash flows and terminal value.

It is not the average of instrument XIRRs.

---

## Portfolio management

## Portfolio weight

Instrument current value as a share of total portfolio current value.

---

## Class weight

Exposure of the relevant investment class relative to total portfolio value.

---

## Target weight

Configured desired allocation for the relevant investment class.

---

## Allocation drift

Difference between actual allocation and target allocation.

---

## Rebalance flag

Signal indicating allocation drift has crossed the current implementation's tolerance.

During the v6 audit, the tolerance remained approximately five percentage points in code.

---

## Harvestable loss

Unrealized loss state that can participate in tax-harvesting analysis under the implemented methodology.

---

## Harvesting priority

Decision-support signal ranking/identifying tax-aware loss-harvesting context.

Not an autonomous trade instruction.

---

## Tax

## LTCG

Long-Term Capital Gain.

Realized or unrealized gain classified as long-term under the implemented holding/tax rules.

---

## STCG

Short-Term Capital Gain.

---

## LTCL

Long-Term Capital Loss.

---

## STCL

Short-Term Capital Loss.

---

## Estimated tax if sold

Modelled tax exposure if an active investment position were realized under current lot/tax state.

---

## After-tax close value

Current market value less modelled tax exposure if sold.

---

## LTCG exemption

Configured exemption amount applied to eligible long-term capital-gain state under the implemented tax model.

---

## Tax harvesting capacity

Modelled capacity for loss state to offset relevant taxable realized gain under the implemented methodology.

Planning metric, not a trade recommendation.

---

## `HARVEST_LOSS`

Tax-action classification indicating a current loss-harvesting opportunity under the implemented deterministic rules.

---

## `HARVEST_LTCG_EXEMPT`

Tax-action classification indicating potential use of remaining LTCG exemption under the implemented rules.

---

## `WAIT_FOR_LTCG`

Tax-action classification indicating the lot is sufficiently close to long-term treatment under the configured waiting threshold.

---

## `HOLD`

Default/no-action tax classification when the implemented harvesting conditions are not met.

---

## FIRE & planning

## FIRE

Financial Independence, Retire Early.

In this project, FIRE refers to a planning model built from connected household wealth, spending, savings, tax, and stochastic assumptions.

---

## FI target

Capital required to support the configured spending base under the model's withdrawal assumptions.

---

## Lean FI

FI target based on a lean/core spending perspective.

---

## Coast FI

Current capital required such that configured future growth can reach the relevant FI target with reduced need for additional contributions.

Highly assumption-sensitive.

---

## FI coverage

Current relevant wealth relative to the FI target.

---

## FI gap

Difference between FI target and current relevant wealth.

---

## Withdrawal rate

Spending relative to the relevant wealth base.

A current withdrawal rate is not automatically a recommended sustainable withdrawal rate.

---

## Runway

Modelled duration for which current resources can support the relevant spending base.

Can be deterministic or stochastic.

---

## FI velocity

Model-derived rate of progress toward financial independence.

Not an investment return.

---

## Wealth velocity

Rate of wealth progression under the implemented planning methodology.

---

## Wealth acceleration

Change in wealth velocity over time.

---

## Stochastic modelling

## Monte Carlo simulation

Repeated pathwise simulation of uncertain financial outcomes under configured assumptions.

Produces scenario distributions rather than predictions.

---

## Market regime

Discrete market state with its own return/volatility assumptions.

Current conceptual regimes include Bull, Bear, and Stagflation.

---

## Markov transition matrix

Probability matrix controlling how the simulated market regime transitions from one period to the next.

---

## Student-t shock

Heavy-tailed random return innovation used to model more extreme outcomes than a Gaussian process with similar variance.

---

## Jump event

Discrete positive/negative shock layered on top of ordinary return dynamics.

---

## Stochastic inflation

Inflation modelled as a varying path rather than one fixed constant.

---

## Human-capital shock

Simulated disruption to future earning/saving capacity, such as unemployment.

---

## Glide path

Rule describing how asset allocation changes through the planning horizon.

---

## Portfolio drag

Recurring cost/expense deducted from gross modelled investment return.

---

## Dynamic withdrawal

Withdrawal policy that can respond to portfolio state rather than using one fixed inflation-adjusted spending path.

---

## Guyton-Klinger-style withdrawal policy

Dynamic withdrawal methodology using guardrail-style adjustments to spending based on portfolio conditions.

The project models these concepts as configurable scenario behaviour.

---

## Sequence-of-returns risk

Risk that the order/timing of returns materially changes outcomes even when long-run average returns are similar.

Especially important around retirement/withdrawal periods.

---

## P10 / P50 / P90

Percentiles of simulated outcome distributions.

For months-to-FI:

- P10 is an earlier simulated percentile,
- P50 is the median,
- P90 is a later simulated percentile.

They are not guaranteed dates or classical confidence intervals.

---

## Probability of success

Fraction of simulated paths satisfying the model's configured success criterion.

It is a conditional model output, not an objective real-world probability.

---

## Terminal wealth

Wealth remaining at the end of the simulation horizon.

The current Gold contract exposes median nominal terminal wealth.

---

## Project-specific terminology

## `Core_Monthly_Fact`

Gold household-month analytical spine combining income, expense, cash-flow, asset, investment, wealth, and macro context.

---

## `Wealth_Asset_Breakdown`

Gold Month × Asset wealth drill-down.

---

## `Cashflow_Activity_Summary`

Gold monthly cash-flow reconciliation mart.

---

## `Investment_Portfolio_Summary`

Gold Month × ISIN portfolio-management mart focused on allocation, drift, and tax-aware action context.

---

## `Investment_By_*`

Family of Gold investment-performance/tax marts published at ISIN, subtype, class, instrument-type, sector, industry, and portfolio grains.

---

## `Wealth_FIRE_Analytics`

Gold monthly FIRE/planning mart combining current-state, deterministic, and selected stochastic outputs.

---

## `Forecast_Tax_Liability`

Gold tax-planning mart.

---

## `Forecast_Budget_Variance`

Gold budget/planning mart.

---

## `FinancialRules`

Validated financial-policy configuration defining household semantics, tax parameters, allocations, FIRE assumptions, and stochastic-model behaviour.

Distinct from operational Settings.

---

## Settings

Operational configuration describing where/how the application runs, including paths, persistence locations, and ingestion policy.

---

## `PersonalFinanceEngine`

Backend facade used by application surfaces to validate configuration, launch pipeline execution, manage snapshots, and communicate with frontends.

---

## `shan-fin`

CLI application entry point.

---

## `shan-fin-gui`

Desktop application entry point.

---

## Semantic caveats

## `Outperformance_Probability`

Historical field name whose current methodology is closer to the fraction of active lots outperforming their benchmark CAGR.

It should not be interpreted as a stochastic forecast probability.

---

## `ISIN_Monthly_Return`

Historical field name whose current portfolio-management calculation is closer to market-value percentage change than a fully cash-flow-adjusted return.

XIRR is the stronger cash-flow-aware return measure.

---

## Documentation vocabulary rules

Throughout the docs:

### "Current"

Means implemented/published in the v6 architecture being documented.

### "Future"

Means roadmap/design direction, not current capability.

### "Observed"

Means sourced or derived directly from financial/market evidence.

### "Reconstructed"

Means calculated from canonical historical financial activity.

### "Modelled"

Means produced by assumptions/methodology, such as estimated tax or FIRE simulation.

### "Canonical"

Means source-specific structure has been resolved into stable financial concepts.

### "Published"

Means part of the physical Silver/Gold/Meta analytical contract, not merely an internal helper calculation.

---

## Related documentation

- [Silver Data Contracts](silver-data-contracts.md)
- [Gold Data Contracts](gold-data-contracts.md)
- [Meta Data Contracts](meta-data-contracts.md)
- [Financial Model](../finance/financial-model.md)
- [Metrics & Methodology](../finance/metrics-and-methodology.md)

[← Reference Home](README.md) · [← Documentation Home](../README.md)
