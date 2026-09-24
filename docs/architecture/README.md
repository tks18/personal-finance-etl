# Architecture

This section explains **how Personal Finance ETL is constructed, how financial state moves through the platform, and why the major architectural boundaries exist**.

The architecture is intentionally local-first and separates raw evidence, ingestion state, canonical financial semantics, analytical computation, warehouse serving, and application consumption.

> **Start here:** [System Architecture](system-architecture.md) gives the complete end-to-end view.

## Guides

| Guide | Purpose |
| --- | --- |
| [System Architecture](system-architecture.md) | Understand the major planes, components, engine boundaries, technologies, and runtime relationships |
| [Data Lifecycle](data-lifecycle.md) | Trace data from source discovery through Raw, Bronze, canonical transformation, analytics, and serving |
| [Warehouse Architecture](warehouse-architecture.md) | Understand Bronze, Silver, Gold, and Meta responsibilities and persistence semantics |
| [Data Model](data-model.md) | Understand canonical dimensions, facts, relationships, and analytical grains |
| [Reliability & Recovery](reliability-and-recovery.md) | Understand transactions, failure handling, persisted raw state, reconstruction, and operational recovery |
| [Design Decisions](design-decisions.md) | Understand the trade-offs behind SQLite + DuckDB, deterministic rebuilds, raw BLOB persistence, process isolation, and other choices |

## Recommended path

```text
System Architecture
        ↓
Data Lifecycle
        ↓
Warehouse Architecture
        ↓
Data Model
        ↓
Reliability & Recovery
        ↓
Design Decisions
```

The recurring architectural principle is:

> **Preserve raw evidence, model financial meaning explicitly, reconstruct derived state deterministically, and publish analytics at the grain required by the decision.**

The architecture documentation focuses on the *why* as much as the *what*. A component diagram is useful; understanding why that component exists is better.

[← Documentation Home](../README.md)
