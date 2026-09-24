# Personal Finance ETL Documentation

Welcome to the technical documentation for **Personal Finance ETL**, a local-first financial data and decision-support platform built around a real personal-finance workload.

The project connects raw financial evidence to household accounting, investment analytics, tax-aware wealth modelling, cash-flow reconciliation, long-range planning, and BI consumption through one end-to-end financial lineage.

The documentation now also records the **project philosophy, roadmap, and engineering journey behind the system**, so the repository explains not only *what* I built, but also *why it exists*, *how I think about it*, and *where I want to take it*.

> **New here?** Start with [Project Overview](about/project.md), then read [System Architecture](architecture/system-architecture.md) and [Data Lifecycle](architecture/data-lifecycle.md).

---

## Documentation map

```text
Project story & engineering journey
        ↓
Raw financial evidence
        ↓
Architecture & data lifecycle
        ↓
Canonical financial model
        ↓
Finance & quantitative methodology
        ↓
Configuration
        ↓
Developer extension points
        ↓
Data contracts & reference
        ↓
Roadmap & future generalization
```

The documentation is organized by **what you are trying to understand or do**, rather than by the Python package tree.

---

## 🚀 Start here

Use these pages if you are new to the project or want to operate the pipeline.

| Guide | What it answers |
| --- | --- |
| [Project Overview](about/project.md) | Why the project exists, what it is today, what it is not, and the philosophy behind it |
| [Installation](getting-started/installation.md) | How to install the package and prepare a local environment |
| [Configuration](getting-started/configuration.md) | How operational settings, paths, mappings, and financial rules fit together |
| [Running the Pipeline](getting-started/running-the-pipeline.md) | How to run the CLI, desktop application, automated execution, and snapshots |

---

## 🏗️ Architecture & data engineering

These documents explain how the platform is constructed and why its major engineering decisions exist.

| Guide | Focus |
| --- | --- |
| [System Architecture](architecture/system-architecture.md) | End-to-end planes, components, engine boundaries, and runtime flow |
| [Data Lifecycle](architecture/data-lifecycle.md) | Source discovery → Raw Store → Bronze → canonical transformations → analytics → serving |
| [Warehouse Architecture](architecture/warehouse-architecture.md) | Raw, Bronze, Silver, Gold, and Meta responsibilities and persistence semantics |
| [Data Model](architecture/data-model.md) | Canonical dimensions, facts, analytical grains, and major relationships |
| [Reliability & Recovery](architecture/reliability-and-recovery.md) | Transaction handling, raw-state recovery, deterministic reconstruction, and failure behaviour |
| [Design Decisions](architecture/design-decisions.md) | Why SQLite + DuckDB, why Silver/Gold rebuild, why raw BLOB persistence, and other trade-offs |

### Core architectural idea

```text
Raw & Control Plane
        ↓
Persistent Bronze
        ↓
Canonical Financial & Semantic Model
        ↓
Investment Quant + Wealth Analytics
        ↓
Silver / Gold / Meta
        ↓
Power BI / CLI / Desktop
```

Source history is incremental where that preserves evidence efficiently. Derived analytical state is rebuilt where deterministic reconstruction simplifies correctness.

---

## 💰 Finance & quantitative methodology

These pages define the financial meaning behind the data.

| Guide | Focus |
| --- | --- |
| [Financial Model](finance/financial-model.md) | Household ledger semantics, income, expenses, transfers, assets, liabilities, and wealth |
| [Metrics & Methodology](finance/metrics-and-methodology.md) | Definitions, formulas, grains, assumptions, interpretation, and limitations of published metrics |
| [Investment Analytics](finance/investment-analytics.md) | FIFO lots, broker reconciliation, shadow benchmarks, XIRR, after-tax returns, drawdown, and aggregation |
| [Cash Flow & Wealth](finance/cashflow-and-wealth.md) | Book vs market wealth, liquidity, savings, cash-flow activity, and reconciliation |
| [Tax Methodology](finance/tax-methodology.md) | Holding-period treatment, realized/unrealized tax state, exemptions, harvesting logic, and jurisdiction-specific assumptions |
| [FIRE Methodology](finance/fire-methodology.md) | Current-state FIRE, deterministic planning, Monte Carlo mechanics, assumptions, outputs, and limitations |

> Financial and stochastic outputs are **decision-support results under explicit assumptions**, not predictions or financial guarantees.

---

## ⚙️ Configuration

Configuration is treated as part of the system's financial semantics, not merely application plumbing.

| Guide | Focus |
| --- | --- |
| [Financial Rules](configuration/financial-rules.md) | Income/expense semantics, asset classifications, cash-flow policy, tax parameters, allocations, macro assumptions, and planning rules |
| [FIRE Configuration](configuration/fire-configuration.md) | Market regimes, inflation, human-capital shocks, glide paths, withdrawal rules, and simulation parameters |

A useful rule of thumb for the architecture is:

> **Parameters belong in configuration. Genuinely different behaviour belongs behind adapters or strategies.**

---

## 🧑‍💻 Developer guides

Use these pages when extending or modifying the platform.

| Guide | Focus |
| --- | --- |
| [Development Guide](developer/development-guide.md) | Package structure, engineering conventions, typing, quality tooling, and development workflow |
| [Adding a Data Source](developer/adding-data-sources.md) | Source discovery, Raw Store registration, extraction, Bronze loading, and canonical transformation |
| [Adding an Asset Pipeline](developer/adding-asset-pipelines.md) | Extending the investment model through the asset-pipeline contract |
| [Adding a Gold Mart](developer/adding-gold-marts.md) | Business purpose → grain → builder → output contract → DDL → Gold publication |

The current implementation is purpose-built around **my financial environment**. Extending it for another user can require source-adapter, mapping, financial-semantic, and jurisdictional customization.

---

## 📖 Data contracts & reference

These pages describe the physical analytical contracts exposed by the current architecture.

| Reference | Focus |
| --- | --- |
| [Silver Data Contracts](reference/silver-data-contracts.md) | The 20 canonical Silver dimensions/reference models and facts |
| [Gold Data Contracts](reference/gold-data-contracts.md) | The 17 decision-support marts, their grains, domains, producers, and major measures |
| [Meta Data Contracts](reference/meta-data-contracts.md) | File registry, run telemetry, row counts, settings, and financial-rules snapshots |
| [Glossary](reference/glossary.md) | Project terminology, financial concepts, architectural vocabulary, and abbreviations |

For important analytical datasets, the reference documentation uses a common contract:

```text
Purpose
Layer
Domain
Grain
Producer
Major inputs
Key fields
Downstream consumers
Assumptions / caveats
```

---

## 🧭 About, philosophy & direction

These pages explain the human and architectural story around the code.

| Guide | Focus |
| --- | --- |
| [Project Overview](about/project.md) | Why I built Personal Finance ETL, what problem it solves, and the philosophy behind the current vertical system |
| [About Me](about/about-me.md) | My path from web development into Python, data engineering, BI, software architecture and the convergence with Chartered Accountancy |
| [Roadmap](about/roadmap.md) | How I plan to harden and generalize the working system through contracts, adapters, strategies and behavioural equivalence |

Together they answer three different questions:

```text
Project Overview
→ Where did this system come from?

About Me
→ Who built it, and how did that engineering path evolve?

Roadmap
→ Where does the platform go from here?
```

---

## 🧭 Choose your path

### I want to understand the whole system

1. [Project Overview](about/project.md)
2. [System Architecture](architecture/system-architecture.md)
3. [Data Lifecycle](architecture/data-lifecycle.md)
4. [Warehouse Architecture](architecture/warehouse-architecture.md)
5. [Financial Model](finance/financial-model.md)

### I am a data or BI engineer

1. [Data Lifecycle](architecture/data-lifecycle.md)
2. [Warehouse Architecture](architecture/warehouse-architecture.md)
3. [Data Model](architecture/data-model.md)
4. [Silver Data Contracts](reference/silver-data-contracts.md)
5. [Gold Data Contracts](reference/gold-data-contracts.md)
6. [Metrics & Methodology](finance/metrics-and-methodology.md)

### I am a Python developer

1. [System Architecture](architecture/system-architecture.md)
2. [Development Guide](developer/development-guide.md)
3. [Adding a Data Source](developer/adding-data-sources.md)
4. [Adding an Asset Pipeline](developer/adding-asset-pipelines.md)
5. [Adding a Gold Mart](developer/adding-gold-marts.md)
6. [Design Decisions](architecture/design-decisions.md)

### I care about the financial model

1. [Financial Model](finance/financial-model.md)
2. [Investment Analytics](finance/investment-analytics.md)
3. [Cash Flow & Wealth](finance/cashflow-and-wealth.md)
4. [Tax Methodology](finance/tax-methodology.md)
5. [FIRE Methodology](finance/fire-methodology.md)
6. [Metrics & Methodology](finance/metrics-and-methodology.md)

### I want to adapt the project for another financial environment

1. [Project Overview](about/project.md)
2. [Roadmap](about/roadmap.md)
3. [Configuration](getting-started/configuration.md)
4. [Financial Rules](configuration/financial-rules.md)
5. [Adding a Data Source](developer/adding-data-sources.md)
6. [Adding an Asset Pipeline](developer/adding-asset-pipelines.md)
7. [Design Decisions](architecture/design-decisions.md)

### I want to understand the engineering journey behind the project

1. [About Me](about/about-me.md)
2. [Project Overview](about/project.md)
3. [Design Decisions](architecture/design-decisions.md)
4. [Roadmap](about/roadmap.md)

---

## Documentation principles

The documentation follows the same philosophy as the software.

### Code is the source of truth

Documentation describes the live implementation and persisted analytical contracts. Historical helpers, stale comments, or previously pruned metrics are not treated as current product capabilities.

### Financial definitions are explicit

Important measures should document their definition, methodology, grain, assumptions, interpretation, and limitations.

### Architecture includes the *why*

Design documentation should explain the problem, decision, implementation, benefits, and trade-offs rather than merely drawing boxes around modules.

### Grain matters

Month, Month × Asset, Date × ISIN, tax lot, category, class, sector, and portfolio are different analytical questions. Documentation should never blur them together.

### Current state and future direction stay separate

The current v6 implementation is a working vertical system. The long-term configuration-, adapter-, and strategy-driven architecture is a roadmap, not something the documentation should pretend already exists.

### First-person rationale, objective methodology

Where a document explains why I built or chose something, I write from my own perspective. Where it defines a contract, formula, or methodology, precision takes priority over personality.

### Personality is welcome; precision wins

The project can have a pulse without turning methodology into meme soup. 😅

---

## Versioning & source of truth

The Markdown files under `docs/` are the **authoritative, version-controlled technical documentation** for the project.

They are intended to serve the same knowledge base across:

```text
GitHub repository
       │
       ├── CLI documentation browser
       ├── Desktop guides
       ├── Packaged distribution
       └── GitHub Wiki / knowledge base
```

The goal is one maintained body of technical knowledge rather than separate documentation universes drifting away from the code.

---

## About the project

Personal Finance ETL is currently a **purpose-built local financial platform** tailored to my financial data sources, financial semantics, and planning requirements.

Its architecture and many of its analytical components are reusable, but deploying it for a different financial environment can require meaningful customization.

The longer-term direction is to progressively extract source-specific and jurisdiction-specific assumptions behind configuration, canonical contracts, adapters, and strategies while preserving the behaviour of the current production workload.

For the deeper story:

- [Project Overview](about/project.md)
- [About Me](about/about-me.md)
- [Roadmap](about/roadmap.md)

---

> **Yes, the documentation has its own architecture now.**
>
> After seeing what happened to the finance pipeline, we are taking no chances. 😎
