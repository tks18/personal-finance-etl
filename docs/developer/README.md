# Developer Guide

This section is for developers who want to **understand, modify, or extend the production architecture**.

Personal Finance ETL is a typed Python application built around explicit financial contracts, source-state management, analytical builders, and separate investment and wealth engines. The current implementation is tailored to my financial environment, so meaningful extensions often involve both software architecture and data semantics.

> **Before extending the code:** read [System Architecture](../architecture/system-architecture.md) and [Data Lifecycle](../architecture/data-lifecycle.md).

## Guides

| Guide | Purpose |
| --- | --- |
| [Development Guide](development-guide.md) | Understand package structure, engineering conventions, typing, tooling, and development workflow |
| [Adding a Data Source](adding-data-sources.md) | Extend discovery, Raw Store registration, extraction, Bronze persistence, and canonical transformation |
| [Adding an Asset Pipeline](adding-asset-pipelines.md) | Add a new investment/asset implementation behind the canonical asset-pipeline contract |
| [Adding a Gold Mart](adding-gold-marts.md) | Add a decision-support dataset from business purpose through grain, builder, DDL, and publication |

## Extension model

```text
External / user-specific behaviour
            ↓
Adapter or Strategy
            ↓
Canonical Contract
            ↓
Reusable Engine
            ↓
Analytical Mart
```

The preferred direction is to keep source-specific behaviour **upstream of canonical contracts** and keep decision-specific publication **downstream in explicit analytical marts**.

## Engineering principles

- Prefer typed contracts over implicit dictionary conventions where boundaries matter.
- Add abstractions where behaviour genuinely varies, not merely to create another interface.
- Preserve canonical financial semantics downstream of source adapters.
- Define analytical grain before writing calculations.
- Treat financial methodology changes as semantic changes, not cosmetic refactors.
- Keep current behaviour reproducible while extracting generality.

The project uses Python 3.13+, Pydantic, Polars, DuckDB, SQLite, multiprocessing, Ruff, strict mypy, and strict Pyright across the core application.

[← Documentation Home](../README.md)
