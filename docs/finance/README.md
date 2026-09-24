# Finance & Quantitative Methodology

This section documents the **financial meaning** of Personal Finance ETL.

It explains how the platform moves from canonical transactions and investment state to household accounting, wealth, tax, portfolio analytics, cash-flow reconciliation, and long-range FIRE planning.

These pages are methodology documentation, not financial advice.

> **Start here:** [Financial Model](financial-model.md) establishes the household and investment concepts used throughout the analytical system.

## Guides

| Guide | Purpose |
| --- | --- |
| [Financial Model](financial-model.md) | Define the household ledger, income, expenses, transfers, assets, liabilities, investments, and wealth semantics |
| [Metrics & Methodology](metrics-and-methodology.md) | Define published measures, formulas, grains, assumptions, interpretation, and limitations |
| [Investment Analytics](investment-analytics.md) | Explain FIFO tax lots, broker reconciliation, shadow benchmarks, XIRR, after-tax performance, drawdown, and aggregation |
| [Cash Flow & Wealth](cashflow-and-wealth.md) | Explain book vs market wealth, savings, liquidity, cash-flow activity, and reconciliation |
| [Tax Methodology](tax-methodology.md) | Explain holding periods, realized/unrealized tax state, exemptions, harvesting logic, and jurisdiction-specific assumptions |
| [FIRE Methodology](fire-methodology.md) | Explain current-state FIRE, deterministic planning, Monte Carlo mechanics, scenario outputs, and limitations |

## Recommended path

```text
Financial Model
      ↓
Cash Flow & Wealth
      ↓
Investment Analytics
      ↓
Tax Methodology
      ↓
FIRE Methodology
      ↓
Metrics & Methodology
```

A few rules apply throughout this section:

- **Grain matters.** A tax lot, ISIN, asset, household month, and portfolio are different analytical objects.
- **Methodology matters.** Metric names are not substitutes for definitions.
- **Assumptions are part of the model.** Tax rates, market regimes, inflation, and FIRE parameters must be interpreted in context.
- **Scenario outputs are not predictions.** Monte Carlo results describe modelled outcomes under configured assumptions.
- **Decision usefulness beats metric collecting.** The serving model intentionally exposes a curated analytical surface.

[← Documentation Home](../README.md)
