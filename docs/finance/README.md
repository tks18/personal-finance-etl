# Finance · Technical specifications

I document the financial semantics of my data platform here: how source events become lots, realized gains, tax events, net-worth series, and financial-independence scenarios. These specifications describe the algorithms and their assumptions; physical schemas live in `reference/`.

## Core financial models

- [Financial Model](financial-model.md)
- [Investment Analytics](investment-analytics.md)
- [Metrics And Methodology](metrics-and-methodology.md)
- [Tax Methodology](tax-methodology.md)
- [Cashflow And Wealth](cashflow-and-wealth.md)
- [Fire Methodology](fire-methodology.md)

## Deep implementation specifications

- [FIFO lot accounting and disposal events](fifo-and-lot-accounting.md)
- [Reconciliation and cost-basis provenance](reconciliation-and-cost-basis.md)
- [Foreign-exchange handling and valuation](fx-methodology.md)
- [Lot-aware benchmark attribution](benchmark-attribution.md)
- [Tax-event provenance and classification](tax-event-provenance.md)
- [FIRE simulations and reproducibility](fire-simulation-and-reproducibility.md)

## How I use these documents

I start with the financial model for the vocabulary and then follow the lot-accounting, FX, benchmark, tax, and FIRE pages for execution-level behavior. For exact output grains and field types I cross-reference the data-contract registry.
