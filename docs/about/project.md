# Project Overview

Personal Finance ETL is a **local-first financial data and decision-support platform** built around a real personal-finance workload.

It began as a practical data-engineering problem: financial information lived across different files, institutions, investment records, mappings, and spreadsheets, while month-end closure required repeatedly reconciling those sources into one trustworthy view.

The project grew from that need.

Today it preserves raw financial evidence, reconstructs canonical household and investment state, applies accounting, tax, portfolio, and planning models, and publishes curated analytical datasets for Power BI, CLI, and desktop consumption.

> This is not a generic consumer-finance product with a demo dataset. It is a production system I built for my own financial environment and continue to use for month-end closure, investment review, and long-range planning.

---

## Why this project exists

The original problem was not "build an ETL framework."

It was:

> **How do I create one reliable financial state from everything that actually happened?**

Answering that properly required more than importing transactions.

A useful month-end view needed to reconcile:

- income and expenses,
- cash and non-cash activity,
- transfers between assets,
- opening and closing balances,
- investment purchases and sales,
- current broker positions,
- market values,
- realized and unrealized tax state,
- benchmark-relative performance,
- cash-flow movement,
- budgets,
- tax exposure,
- and progress toward long-term financial independence.

Once those concepts needed to agree with one another, the project stopped being a collection of spreadsheets and became a data platform.

---

## What the system does

At a high level, the system turns heterogeneous financial evidence into a coherent analytical state.

```text
Raw financial sources
        ↓
Durable source evidence
        ↓
Persistent ingestion state
        ↓
Canonical household & investment model
        ↓
Accounting + portfolio + tax analytics
        ↓
Market-adjusted wealth
        ↓
Cash-flow & planning models
        ↓
FIRE scenario analysis
        ↓
Decision-support marts
        ↓
Power BI • CLI • Desktop
```

The important part is not any one calculator.

The same underlying financial state flows through the household ledger, investment engine, tax model, cash-flow model, wealth model, and FIRE engine.

That shared lineage is what allows the platform to answer increasingly sophisticated questions without creating a separate truth for every dashboard.

---

## What I use it for

### Month-end financial close

The system helps consolidate and reconcile the month's financial activity into a consistent household state.

That includes:

- income and expense activity,
- asset transfers,
- cash movement,
- opening and closing balances,
- investment balances,
- book and market wealth,
- and analytical reconciliation.

The objective is not merely to categorize transactions. It is to finish the month with a financial state that can support downstream analysis.

### Wealth monitoring

The platform distinguishes between **ledger-derived book wealth** and **market-adjusted wealth**.

This allows the analytical model to separate financial activity from market movement and answer questions such as:

- How much of wealth growth came from savings?
- How much came from investment appreciation?
- What is liquid versus illiquid?
- How are liabilities changing?
- How much runway does the current balance sheet provide?

### Investment planning

Investment activity is reconstructed at tax-lot level using FIFO accounting and reconciled against broker-reported state.

The platform can then reason about:

- invested and current value,
- realized and unrealized gains/losses,
- holding periods,
- estimated tax state,
- XIRR and after-tax XIRR,
- benchmark-relative performance,
- drawdown,
- portfolio allocation,
- allocation drift,
- and tax-aware harvesting opportunities.

### Cash-flow understanding

The platform separates accounting activity from actual cash movement.

Configured cash pools allow activity to be classified across operating, investing, financing, and internal-transfer flows, then reconciled against opening and closing cash balances.

That produces a much more useful answer than "income minus expenses."

### Financial planning

Budgeting, tax forecasting, savings behaviour, liquidity, and financial-independence metrics all operate on the same reconstructed household state.

The goal is to turn historical data into useful planning context without creating a second disconnected planning model.

### FIRE scenario analysis

The FIRE engine combines current financial state with configurable assumptions to model:

- FI targets,
- FI coverage and gap,
- runway,
- savings requirements,
- deterministic FI trajectories,
- and stochastic distributions of FI timing and terminal wealth.

The Monte Carlo model can include market regimes, fat-tailed shocks, jump events, stochastic inflation, human-capital shocks, glide paths, portfolio drag, and dynamic withdrawal rules.

These outputs are planning guidance under explicit assumptions, not predictions or guarantees.

---

## The project through five engineering lenses

The repository is useful as a financial system, but it is also an end-to-end engineering project spanning several disciplines.

### 🏗️ Data engineering

The data-engineering layer handles more than file import.

It includes:

- source discovery,
- configurable content-change detection,
- SHA-256 source fingerprints,
- durable raw BLOB persistence,
- explicit ingestion synchronization state,
- full-replacement and file-aware incremental Bronze strategies,
- virtual benchmark artifacts,
- source lineage,
- deterministic downstream reconstruction,
- recovery from persisted raw evidence,
- and local analytical persistence.

A key architectural decision is the asymmetric use of state:

> **Source history is incremental where that preserves evidence efficiently. Derived analytical state is rebuilt where deterministic reconstruction simplifies correctness.**

### 📊 BI & analytics engineering

The platform has an explicit semantic and serving model.

Silver represents canonical financial and analytical state through dimensions, reference models, and facts.

Gold publishes decision-support marts at deliberately different grains, including:

- Month,
- Month × Asset,
- Month × Category,
- Month × ISIN,
- Date × ISIN,
- Date × Class,
- and Portfolio.

The system does not force every analytical question into one universal fact table.

This allows Power BI to consume business-ready models while keeping source-specific complexity upstream.

### 🐍 Python & software engineering

The project is structured as a typed Python application rather than a collection of scripts or notebooks.

Engineering patterns include:

- validated Pydantic configuration,
- structural Protocols,
- strategy-style asset pipelines,
- builder-based analytical composition,
- Polars LazyFrames,
- multiprocessing,
- process-pool execution,
- backend/frontend separation,
- application-coordinated transactions,
- snapshot and recovery workflows,
- Ruff,
- strict mypy,
- and strict Pyright across the core application.

The architecture deliberately avoids abstraction for abstraction's sake. Extension seams exist where behaviour genuinely varies.

### 💰 Financial engineering

The financial model includes:

- household ledger semantics,
- cash and non-cash activity,
- core and non-core expense treatment,
- transfers and opening balances,
- book versus market wealth,
- liquidity and liabilities,
- FIFO tax lots,
- broker-authoritative position reconciliation,
- realized and unrealized tax state,
- after-tax valuation,
- benchmark-relative investment analysis,
- direct cash-flow reconciliation,
- budgeting,
- tax forecasting,
- and wealth planning.

The objective is coherent financial state, not maximum metric count.

### 🔥 Quantitative planning

The quantitative layer focuses on decision-useful measures and scenario modelling.

Current serving analytics include concepts such as:

- CAGR,
- XIRR,
- after-tax XIRR,
- benchmark XIRR,
- active return,
- max drawdown,
- allocation and drift,
- FI coverage,
- FI gap,
- runway,
- FI timing distributions,
- modelled probability of success,
- and median terminal wealth.

Earlier versions carried a broader set of quantitative ratios. The current architecture intentionally publishes a smaller analytical surface aligned to the decisions the system is actually used to support.

**Compute richly. Publish selectively.**

---

## Architecture philosophy

Several principles emerged naturally as the project evolved.

### Preserve evidence before transforming it

Raw financial artifacts are persisted independently from derived analytical state.

The Raw Document Store is therefore not merely a staging area. It is a provenance and recoverability boundary.

### Give technologies specific jobs

SQLite and DuckDB coexist because they solve different problems.

**SQLite** owns the raw/control workload: source registry, BLOB persistence, hashes, and synchronization state.

**DuckDB** owns the analytical workload: Bronze, Silver, Gold, Meta, and BI-serving data.

**Polars** owns transformation and analytical computation.

**Numba/NumPy** handle numerically intensive stochastic simulation.

The architecture uses multiple tools because their responsibilities differ, not because collecting databases is a hobby.

### Separate source semantics from financial semantics

A broker statement format is not a financial model.

Source-specific extraction and transformation happen upstream so analytical engines can work with canonical concepts such as:

- income,
- expense,
- asset,
- purchase,
- sale,
- benchmark,
- tax lot,
- and market value.

This canonical boundary is one of the most important extension seams in the system.

### Respect analytical grain

A tax lot and a household month are not interchangeable analytical objects.

Neither are:

- asset,
- ISIN,
- category,
- sector,
- class,
- or portfolio.

The platform therefore publishes separate contracts at the grain appropriate to the question being answered.

### Prefer reproducibility over downstream incremental complexity

Bronze retains persistent incremental source state.

Silver and Gold are reconstructed deterministically from that state.

For a local personal-finance workload, this reduces stale-state and dependency complexity while preserving source history.

### Treat configuration as financial policy

Configuration is not limited to paths and filenames.

`FinancialRules` expresses financial semantics such as:

- income/expense treatment,
- asset classifications,
- cash-flow policy,
- investment classifications,
- target allocations,
- tax parameters,
- macro assumptions,
- FIRE assumptions,
- and stochastic-model parameters.

The long-term architectural rule is:

> **Parameters belong in configuration. Genuinely different behaviour belongs behind adapters or strategies.**

---

## What the project is today

The current v6 architecture is a **working vertical implementation**.

Large parts of the engine are reusable, including:

- raw persistence,
- ingestion state management,
- pipeline orchestration,
- warehouse lifecycle,
- canonical modelling patterns,
- investment analytical primitives,
- wealth analytics,
- FIRE simulation,
- and application structure.

Many financial semantics are already configurable.

However, the current implementation remains tailored to my environment in areas such as:

- bank and broker source contracts,
- statement layouts,
- source mappings,
- some asset transformations,
- Indian tax behaviour,
- and selected analytical policies.

For another developer, adopting the project today is therefore an **engineering and data-integration exercise**, not a turnkey personal-finance deployment.

That limitation is intentional to state clearly.

---

## What the project is not

### It is not a SaaS finance product

There is no claim that arbitrary users can connect arbitrary institutions and immediately receive correct analytics.

### It is not a cloud data platform

The architecture is deliberately local-first.

Financial data and analytical computation are intended to remain on the user's machine.

### It is not a collection of independent finance calculators

The household, investment, tax, cash-flow, and FIRE models share one financial lineage.

### It is not a prediction engine

Monte Carlo and FIRE outputs describe modelled outcomes under configured assumptions.

They do not predict markets, retirement dates, or future wealth.

### It is not trying to publish every finance ratio available

The analytical serving layer is intentionally curated around decision usefulness.

If a metric does not improve the real workflow, it does not earn permanent dashboard real estate simply because a formula exists for it.

---

## Evolution of the project

The project has gone through several conceptual stages.

```text
Stage 1
Consolidate financial data
        ↓
Stage 2
Build a canonical warehouse
        ↓
Stage 3
Reconstruct investment state
        ↓
Stage 4
Add portfolio, tax, and wealth analytics
        ↓
Stage 5
Model cash flow and long-range planning
        ↓
Stage 6
Prune analytical noise and strengthen decision support
        ↓
Future
Generalize source and policy assumptions behind configuration,
canonical contracts, adapters, and strategies
```

That evolution matters.

The current architecture was not designed in isolation and then given a synthetic workload. It grew against a real operating problem and was repeatedly refactored as that problem became better understood.

---

## Long-term direction

The long-term goal is to preserve the current analytical behaviour while progressively extracting assumptions from the vertical implementation.

The target is conceptually:

```text
Current engine + my source assumptions
                 │
                 ▼
          Expected results
                 ▲
                 │
Future generic engine + my configuration
```

The migration strategy is intentionally incremental:

1. Identify an embedded assumption.
2. Characterize its current behaviour.
3. Move parameters into validated configuration where appropriate.
4. Move genuinely different behaviour behind an adapter or strategy.
5. Run the existing financial environment through the generalized path.
6. Reconcile the results.
7. Repeat.

Likely future extension boundaries include:

- bank adapters,
- broker adapters,
- asset pipelines,
- market-data providers,
- tax strategies,
- reconciliation policies,
- and configurable analytical-mart publication.

The goal is not "everything in YAML."

A 4,000-line configuration file wearing a fake moustache is still programming.

---

## Who this repository is for

### For me

It is an operational financial system used for month-end close, investment planning, and long-range financial guidance.

### For data and BI engineers

It demonstrates source-state management, incremental ingestion, canonical modelling, analytical grains, warehouse layering, lineage, recovery, and decision-oriented serving marts.

### For Python developers

It demonstrates typed application architecture, validated configuration, strategy seams, analytical builders, multiprocessing, process isolation, transaction handling, and multiple application surfaces.

### For finance and quantitative readers

It demonstrates household accounting, investment-lot reconstruction, benchmark-relative performance, tax-aware valuation, cash-flow reconciliation, wealth planning, and stochastic FIRE modelling.

### For developers who want to extend it

It provides a working vertical system with identifiable seams for source adapters, asset pipelines, financial policies, and analytical publication.

It also provides plenty of places where meaningful customization is still required. That is part of the current architecture, not something hidden behind the README.

---

## Documentation philosophy

The project documentation follows a few rules.

**The code and persisted analytical contracts are the source of truth.**

**Financial definitions should be explicit about methodology, grain, assumptions, and limitations.**

**Architecture documentation should explain why a decision exists, not merely where a class lives.**

**Current implementation and future roadmap should never be presented as the same thing.**

**Personality is welcome, but precision wins.**

The deeper technical documentation begins with:

- [System Architecture](../architecture/system-architecture.md)
- [Data Lifecycle](../architecture/data-lifecycle.md)
- [Financial Model](../finance/financial-model.md)
- [Investment Analytics](../finance/investment-analytics.md)
- [FIRE Methodology](../finance/fire-methodology.md)

Return to the [Documentation Home](../README.md) for the full documentation map.

---

## A note from the me

This project began because I wanted a better answer to a very ordinary question:

> **Where exactly do I stand financially?**

Apparently my answer required SQLite, DuckDB, Polars, FIFO tax lots, benchmark shadow portfolios, a financial semantic layer, Power BI marts, and a Numba Monte Carlo engine.

Things may have escalated slightly. 😅

But that is also what makes the project useful to me: it was not built to demonstrate an architecture diagram. The architecture emerged because I kept asking harder questions of real financial data.
