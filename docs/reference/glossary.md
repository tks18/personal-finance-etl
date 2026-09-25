# Glossary

This glossary defines project-specific terms as they are used in Personal Finance ETL.

It is not intended to replace general finance, accounting, Python, or data-engineering references.

---

## Architecture & data engineering

## Analytical plane

The DuckDB side of the architecture:

```text
Bronze
Silver
Gold
Meta
```

It owns persistent analytical state, not authoritative historical run state.

---

## Artifact

A source unit registered in the SQLite Control Plane.

An artifact can be:

```text
physical file
or
virtual provider/API payload
```

It has identity, hash, category, payload state, and Bronze synchronization state.

---

## Bronze

Persistent source-shaped analytical state in DuckDB.

Bronze avoids repeatedly extracting unchanged historical evidence while preserving enough source identity for file-aware replacement.

Bronze is **not** canonical finance.

---

## Canonical contract

A stable downstream financial/data concept produced after source-specific normalization.

Examples:

```text
income transaction
expense transaction
investment purchase
investment sale
market observation
```

Canonical contracts form the anti-corruption boundary between messy sources and reusable engines.

---

## Control Plane

The authoritative SQLite subsystem owning:

```text
artifacts
payloads
sync state
runs
failures
Settings snapshots
FinancialRules snapshots
execution logs
```

It is operational infrastructure, not a warehouse layer.

---

## Data Contract

Explicit metadata describing a persistent Silver/Gold analytical output.

```python
@dataclass
class DataContract:
    contract_id: str
    layer: str
    physical_table: str
    domain: str
    grain: str
    producer: str
    publication_order: int
```

---

## Deterministic rebuild

Reconstructing derived analytical state from complete upstream state rather than incrementally patching every downstream dependency.

Silver and Gold use this approach.

---

## Gold

Decision-support serving layer in DuckDB.

Gold marts have explicit:

```text
purpose
grain
producer
physical contract
```

They exist for recurring analytical decisions, not merely because an intermediate DataFrame exists.

---

## Grain

What one row represents.

Examples:

```text
Month
Month × Asset
Date × ISIN
Date × ISIN × Lot
```

Grain is part of metric meaning.

---

## Meta

Lean DuckDB schema containing current analytical telemetry:

```text
m_File_Registry
m_Table_Row_Counts
m_Financial_Rules
m_Settings
```

Meta is a projection, not the historical operational authority.

---

## `PENDING_BRONZE`

Control Plane artifact state meaning:

> raw evidence exists, but successful Bronze synchronization is not yet recorded.

---

## `SYNCED`

Control Plane artifact state meaning:

> the artifact has successfully reached Bronze.

---

## Silver

Canonical financial/reference contract layer in DuckDB.

Silver contains stable dimensions/reference models and facts consumed by analytical engines/Gold.

---

## Virtual artifact

Provider/API-derived evidence injected into the same Control Plane lifecycle as physical files.

Canonical identity:

```text
virtual://<category>/<filename>
```

---

## Software architecture

## Adapter

A boundary that translates an external/source-specific interface into the application's expected form.

Use an adapter when behaviour/shape differs, not merely when a value differs.

---

## Facade

A simplified interface over a subsystem.

`ControlPlane` is a facade over:

```text
SQLiteManager
ArtifactRepository
RunRepository
FileSyncService
```

---

## Repository

A component that owns persistence access for a particular operational responsibility.

Examples:

```text
ArtifactRepository
RunRepository
```

---

## Strategy

An interchangeable behavioural implementation.

A strategy is appropriate when the algorithm genuinely differs.

Do not replace behavioural variation with configuration spaghetti.

---

## LazyFrame

Polars deferred query representation.

LazyFrames allow expressions to remain composable and optimizable before materialization.

---

## Publication order

Explicit integer ordering in `DataContract` used by Silver/Gold loaders to publish registered contracts deterministically.

---

## Household finance

## Book wealth

Wealth reconstructed from household ledger/accounting state before market-value overlays.

---

## Market wealth

Household wealth after replacing/overlaying investment book state with market valuation.

---

## After-tax wealth

Market wealth adjusted for estimated embedded investment tax under the implemented liquidation assumptions.

It is modelled economic state, not observed tax-paid state.

---

## Cash pool

FinancialRules-defined set of assets/accounts treated as cash for direct cash-flow reconciliation.

---

## Core expense

Expense classified as part of the sustainable/essential spending base used by selected planning/FIRE methodology.

The exact classification is policy.

---

## Non-cash activity

Economic income/expense that does not directly move the configured cash pool in the same way as ordinary cash transactions.

---

## Opening balance

State initialization for an asset/account when complete lifetime transaction history is unavailable.

An opening balance is not income.

---

## Transfer

Internal movement between household-controlled assets.

A transfer does not create household income or expense by itself.

---

## Investment analytics

## Active lot

FIFO tax lot with remaining quantity at the current valuation date.

---

## FIFO

First-In, First-Out lot-accounting methodology.

Sales consume the oldest active acquisition inventory first.

---

## Tax lot

A quantity of an investment associated with acquisition state such as:

```text
purchase date
quantity
cost basis
benchmark exposure
```

Lot state is necessary for holding-period and tax-aware analytics.

---

## Broker reconciliation

Adjustment of reconstructed current investment state against broker-reported authoritative current quantity/cost where transaction history is incomplete.

It anchors current truth without pretending missing historical evidence was observed.

---

## Shadow benchmark portfolio

Benchmark-equivalent capital state created at the same timing as real investment capital.

It preserves capital-deployment timing for benchmark comparison.

---

## XIRR

Cash-flow-aware annualized return for irregularly dated cash flows.

XIRR is non-additive and should be reconstructed at the target analytical grain.

---

## After-Tax XIRR

XIRR using estimated after-tax terminal value instead of pre-tax market terminal value.

---

## Benchmark XIRR

XIRR reconstructed from the shadow benchmark capital history.

---

## Active Return

Benchmark-relative return difference using compatible return methodology.

Descriptive, not a forecast of future alpha.

---

## Max Drawdown

Largest historical decline from a prior peak in a value series.

A historical path metric, not a prediction of future loss.

---

## Outperforming Lot Ratio

```text
Active Lots Outperforming Benchmark / Active Lots
```

Descriptive current lot ratio.

Not a probability forecast.

---

## Monthly Market Value Change

Month-over-month percentage change in market value.

It is intentionally not called monthly return because capital flows can affect market value.

---

## Tax

## Holding classification

Tax treatment assigned from asset tax type/subtype, acquisition date, realization/valuation date, and holding duration under the implemented rules.

---

## Realized tax state

Tax-relevant state associated with an actual disposal.

---

## Unrealized tax-if-sold

Estimated tax state if an active lot were realized at the valuation date/price.

Not an observed payable tax amount.

---

## Reconciliation lot

Inventory introduced/adjusted to reconcile current broker state when historical transactions are incomplete.

Useful for current-state correctness but not equivalent to observed acquisition history.

---

## BI & analytics

## Additive measure

Can be summed across compatible dimensions/grain.

Example:

```text
transaction amount
```

---

## Semi-additive measure

Can aggregate across some dimensions but not others.

Example:

```text
balance across assets at one date
```

but not balance summed across time.

---

## Non-additive measure

Requires methodology at the target grain rather than simple summation/averaging.

Examples:

```text
XIRR
CAGR
Max Drawdown
weights
rates
```

---

## Mart

Decision-oriented physical analytical contract, usually in Gold.

A mart should answer a recurring analytical question.

---

## FIRE & quantitative planning

## FIRE

Financial Independence / Retire Early.

In this project, FIRE is a planning methodology downstream of reconstructed household/investment state.

---

## FI target

Deterministic wealth target implied by configured expense and withdrawal assumptions.

Renderer-safe conceptual equation:

```text
FI Target = Annual Core Expense / Withdrawal Rate
```

---

## Market regime

Configured stochastic state such as:

```text
Bull
Bear
Stagflation
```

with associated return/volatility/inflation assumptions.

---

## Markov transition

Regime transition model where the probability of the next regime depends on the current regime.

---

## Fat tail

Return-distribution assumption that assigns more probability to extreme outcomes than a simple Gaussian model.

---

## Jump event

Discrete shock/crash component modelled separately from ordinary continuous volatility.

---

## Human-capital shock

Scenario affecting employment/income/contribution capacity during accumulation.

---

## Glide path

Configured evolution of target asset allocation through time or FI proximity.

---

## Portfolio drag

Configured reduction from gross market return to represent implementation frictions/costs.

---

## Dynamic withdrawal

Post-FI withdrawal policy that can adjust spending based on portfolio/market state rather than following one rigid path.

---

## P10 / P50 / P90

Percentiles of the simulation distribution.

Their interpretation depends on the metric.

For time to FI:

```text
lower
→ earlier
```

For terminal wealth:

```text
higher
→ more wealth
```

---

## Modelled probability of success

```text
Successful Simulation Paths / Total Simulation Paths
```

Probability inside the configured simulation model.

Not an externally calibrated prediction of real-world success.

---

## Provenance & reliability

## Run

One end-to-end pipeline execution registered in the Control Plane.

---

## Run lifecycle

```text
STARTED
→ RUNNING
→ COMMITTING
→ SUCCESS

or

RUNNING / COMMITTING
→ FAILED
```

---

## Configuration snapshot

Content-addressed immutable representation of operational Settings used by a run.

---

## FinancialRules snapshot

Content-addressed immutable representation of financial policy used by a run.

---

## Application-coordinated transaction

The orchestrator coordinates SQLite and DuckDB transaction boundaries.

This is not distributed two-phase commit.

---

## Recoverability

Ability to reconstruct derived analytical state from surviving authoritative evidence.

Recoverability is not the same as immutable historical replay.

---

## Historical reproducibility

Ability to recreate a past result using the same evidence, configuration, code, schema, and external assumptions.

The current system records strong provenance but does not claim fully immutable historical replay.

---

## Documentation

## Documentation manifest

`docs/manifest.json`.

Defines section/page discovery and order for packaged documentation.

---

## `DocsCatalog`

Application component that converts the documentation manifest into navigable entries.

---

## `DocsRenderer`

Shared rendering layer used by the application's documentation surfaces.

---

## Documentation v2

Current editorial philosophy:

> **Explain less. Show more. Prove the architecture with production code. Connect the pieces with diagrams. Use prose for reasoning code cannot communicate.**

---

## Related documentation

- [System Architecture](../architecture/system-architecture.md)
- [Financial Model](../finance/financial-model.md)
- [Metrics & Methodology](../finance/metrics-and-methodology.md)
- [Meta & Control-Plane Data Contracts](meta-data-contracts.md)

[← Reference Home](README.md) · [← Documentation Home](../README.md)
