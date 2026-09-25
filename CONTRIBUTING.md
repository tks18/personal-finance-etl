# Contributing to Personal Finance ETL

Thank you for considering a contribution.

Personal Finance ETL is a local-first financial data platform. Changes can affect not only software behaviour, but also reconstructed financial state, analytical contracts, tax treatment, portfolio metrics, and planning outputs.

> **Make the smallest coherent change, preserve financial truth unless methodology is intentionally changing, and make the impact inspectable.**

Start with the [Developer Guide](docs/developer/development-guide.md), [System Architecture](docs/architecture/system-architecture.md), [Design Decisions](docs/architecture/design-decisions.md), and [Documentation Portal](docs/README.md).

## Before you change code

Identify the boundary that owns the change:

```text
new source/provider behaviour      → adapter / extractor
new asset-specific behaviour       → asset pipeline
same behaviour, different value    → configuration / reference state
different financial algorithm      → strategy / engine behaviour
new recurring decision surface     → Gold mart / analytical contract
operational lifecycle/provenance   → Control Plane
```

Avoid spreading source-specific conditions through canonical financial engines.

## Financial behaviour is part of the contract

For infrastructure, performance, refactoring, documentation, and other non-methodology changes, existing financial outputs should reconcile with the baseline.

Relevant checks can include:

```text
positions
FIFO lot state
realized / unrealized state
tax state
XIRR / benchmark state
household net worth
cash-flow reconciliation
FIRE outputs
Silver / Gold row counts
```

If a change intentionally modifies financial methodology, explain the previous methodology, the new methodology, why the change is correct, and which outputs are expected to move.

## Respect analytical grain

State what one row represents before adding or changing an analytical dataset.

Non-additive metrics such as XIRR, CAGR, drawdown, rates, and weights require target-grain methodology.

```text
Portfolio XIRR ≠ average(ISIN XIRR)
```

## Persistent contracts require coordinated changes

When changing Silver or Gold, review:

```text
builder output
DataContract registry
DuckDB DDL
publication order
Meta row-count telemetry
Power BI consumers
reference documentation
```

A persisted column rename or grain change is an interface change once downstream consumers rely on it.

## Failure semantics matter

Do not catch exceptions merely to keep a run moving. Ask whether partial output is financially valid.

```text
19 successful instruments
+ 1 silently missing instrument
≠ successful portfolio
```

## Ownership boundaries

SQLite Control Plane is authoritative for raw artifacts/payloads, Bronze sync state, runs, failures, logs, and configuration provenance.

DuckDB owns Bronze, Silver, Gold, and lean current-state Meta.

For variation:

```text
same algorithm, different value → configuration
different algorithm/lifecycle   → strategy, adapter, pipeline, or engine boundary
```

## Development workflow

```text
define problem
→ identify owning boundary
→ implement smallest coherent change
→ run static quality checks
→ run representative pipeline
→ reconcile financial outputs
→ review contracts and documentation
```

Use the quality commands configured by the repository, including Ruff, mypy, and Pyright.

## Documentation

```text
source code → implementation ground truth
/docs       → canonical technical documentation
Wiki        → guided exploration
README      → public showcase / router
```

Update documentation when implementation or methodology changes, without duplicating the same material across every surface.

## Pull requests

Keep PRs focused. Explain what changed, why, which boundary owns it, whether financial truth intentionally changes, how it was validated, and whether persisted contracts or documentation changed.

Use the repository pull-request template.

## Financial data and privacy

Never attach real personal financial data to issues, pull requests, discussions, fixtures, screenshots, or logs.

Use minimal synthetic or thoroughly sanitized examples.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and sensitive-data guidance.

## Contribution principle

Improve financial correctness, inspectability, recoverability, extensibility, and decision usefulness without obscuring the boundaries that make the system understandable.
