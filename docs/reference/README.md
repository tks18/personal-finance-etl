# Reference

Reference documentation describes **what the persisted analytical contracts actually are**.

Minimal storytelling. Maximum inspectability.

```text
Logical contract
      ↓
DataContract registry
      ↓
Physical schema
      ↓
Producer
      ↓
Grain
      ↓
Consumers
```

## Current physical contract surface

| Layer | Current scope |
| --- | ---: |
| Silver | **20 contracts** |
| Gold | **17 marts** |
| DuckDB Meta | **lean latest-run analytical projection** |
| SQLite Control Plane | **authoritative operational history and provenance** |

## Guides

| Reference | Focus |
| --- | --- |
| [Silver Data Contracts](silver-data-contracts.md) | Canonical dimensions/reference models, facts and lot analytics |
| [Gold Data Contracts](gold-data-contracts.md) | Decision-support marts, grains, producers and key measures |
| [Meta Data Contracts](meta-data-contracts.md) | Lean DuckDB Meta plus its relationship to the authoritative Control Plane |
| [Glossary](glossary.md) | Project-specific architecture, finance and analytical terminology |

## What a contract should tell you

```text
Layer
Domain
Physical table
Grain
Producer
Major inputs
Key fields
Aggregation semantics
Consumers
Caveats
```

The substantive reference pages pair registry declarations with physical schema and methodology where useful.

[← Documentation Home](../README.md)
