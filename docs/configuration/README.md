# Configuration

This section explains how Personal Finance ETL separates **operational configuration** from **financial policy**.

Paths, source locations, database settings, and ingestion behaviour answer *how the application runs*. Financial classifications, tax parameters, allocations, macro assumptions, and FIRE parameters answer *what the financial model means*.

Keeping those concerns separate is an important architectural boundary.

## Guides

| Guide | Purpose |
| --- | --- |
| [Financial Rules](financial-rules.md) | Configure income/expense semantics, assets, cash-flow policy, investments, allocations, tax, macro assumptions, and planning rules |
| [FIRE Configuration](fire-configuration.md) | Configure market regimes, inflation, human-capital shocks, glide paths, dynamic withdrawals, and Monte Carlo behaviour |
| [Operational Configuration](../getting-started/configuration.md) | Configure paths, source inputs, database locations, mappings, and runtime settings |

## Recommended path

```text
Operational Configuration
          ↓
Financial Rules
          ↓
FIRE Configuration
```

The long-term configuration philosophy is:

> **Parameters belong in configuration. Genuinely different behaviour belongs behind adapters or strategies.**

Not every difference should become another TOML key. Source parsers, jurisdictional tax behaviour, and fundamentally different analytical logic are better represented through explicit extension boundaries.

[← Documentation Home](../README.md)
